"""Copy a beta SQLite database into a migrated, empty PostgreSQL database.

Reads SQLite in read-only mode and refuses to overwrite target data. Private
document files must be copied separately into the protected upload volume.
"""
import argparse
from pathlib import Path
import sqlite3
import sys
from sqlalchemy import create_engine, inspect, select, func, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Base, engine


def import_beta(source_path, include_demo=False):
    source_path = Path(source_path).resolve(strict=True)
    if engine.dialect.name != 'postgresql': raise RuntimeError('Target must be PostgreSQL')
    source_engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(source_path.as_uri()+'?mode=ro', uri=True))
    try:
        source_tables = set(inspect(source_engine).get_table_names())
        if not {'users', 'organizations', 'jobs'}.issubset(source_tables):
            raise RuntimeError('Source is not a recognized SIVRCE beta database')
        with source_engine.connect() as source, engine.begin() as target:
            if 'alembic_version' not in inspect(target).get_table_names(): raise RuntimeError('Migrate target first')
            for table in Base.metadata.sorted_tables:
                if target.scalar(select(func.count()).select_from(table)): raise RuntimeError('Target must be empty')
            if not include_demo and 'organizations' in source_tables:
                if source.scalar(text('SELECT COUNT(*) FROM organizations WHERE demo = 1')):
                    raise RuntimeError('Source has demo organizations; --include-demo is for isolated development only')
            counts = {}
            for table in Base.metadata.sorted_tables:
                if table.name not in source_tables: continue
                if table.name in {'auth_sessions', 'action_tokens', 'team_invites', 'mail_outbox'}: continue
                names = {col['name'] for col in inspect(source_engine).get_columns(table.name)}
                columns = [col for col in table.columns if col.name in names]
                rows = [dict(row) for row in source.execute(select(*columns)).mappings()]
                if rows: target.execute(table.insert(), rows)
                counts[table.name] = len(rows)
            for table in Base.metadata.sorted_tables:
                if 'id' not in table.c: continue
                quoted = target.dialect.identifier_preparer.quote(table.name)
                target.execute(text(f"SELECT setval(pg_get_serial_sequence(:name, 'id'), COALESCE((SELECT MAX(id) FROM {quoted}), 1), EXISTS(SELECT 1 FROM {quoted}))"), {'name': quoted})
            return counts
    finally:
        source_engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-db', required=True)
    parser.add_argument('--include-demo', action='store_true')
    args = parser.parse_args()
    counts = import_beta(args.source_db, args.include_demo)
    print('Imported rows: '+str(sum(counts.values())))
    print('Private document files were not copied. Preserve their object names in protected storage.')
