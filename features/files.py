"""ClamAV INSTREAM integration; production fails closed without a scanner."""
import os
import socket
import struct
from fastapi import HTTPException


def scan_pdf(content):
    host = os.getenv('CLAMAV_HOST')
    if not host:
        if os.getenv('APP_ENV') == 'production':
            raise HTTPException(503, 'დოკუმენტების შემოწმება დროებით მიუწვდომელია')
        return 'development-unscanned'
    try:
        with socket.create_connection((host, int(os.getenv('CLAMAV_PORT', '3310'))), timeout=15) as connection:
            connection.sendall(b'zINSTREAM\0')
            for offset in range(0, len(content), 65536):
                chunk = content[offset:offset+65536]
                connection.sendall(struct.pack('!I', len(chunk))+chunk)
            connection.sendall(struct.pack('!I', 0))
            result = b''
            while b'\0' not in result and len(result) < 4096:
                data = connection.recv(4096)
                if not data: break
                result += data
    except OSError:
        raise HTTPException(503, 'დოკუმენტის შემოწმება ვერ დასრულდა')
    if result.strip(b'\0\r\n') != b'stream: OK':
        raise HTTPException(422, 'დოკუმენტმა უსაფრთხოების შემოწმება ვერ გაიარა')
    return 'clean'
