"""CLI entry point kept separate so the models module is imported exactly once.

  python -m features.voices_cli seed | refresh [max_age_minutes] | transcribe
"""
import sys
import server  # noqa: F401  (registers routers; features.voices is imported through it)
from features.voices import main

sys.exit(main(sys.argv))
