"""Versioned JSON fingerprint shared with the TypeScript SDK.

This is not the native contract's catalogDigest or Studio's digest encoding.
It is deliberately named so those hashes cannot be accidentally interchanged.
"""
import hashlib
import math
import struct

ENCODING = 'ocp-json-binary64/1'


def fingerprint(value):
    chunks = [ENCODING.encode('ascii') + b'\0']
    size = len(chunks[0])

    def emit(data):
        nonlocal size
        size += len(data)
        if size > 1048576:
            raise ValueError('FINGERPRINT_TOO_LARGE')
        chunks.append(data)

    def string(text):
        try:
            data = text.encode('utf-8', errors='strict')
        except UnicodeError:
            raise ValueError('INVALID_UNICODE') from None
        emit(b's' + struct.pack('>I', len(data)) + data)

    def walk(item, depth=0):
        if depth > 64:
            raise ValueError('FINGERPRINT_TOO_DEEP')
        if item is None:
            emit(b'n')
        elif type(item) is bool:
            emit(b't' if item else b'f')
        elif type(item) in (int, float):
            if (abs(item) > 9007199254740991 or not math.isfinite(item)):
                raise ValueError('UNSAFE_NUMBER')
            emit(b'd' + struct.pack('>d', float(item) if item else 0.0))
        elif type(item) is str:
            string(item)
        elif type(item) is list:
            emit(b'a' + struct.pack('>I', len(item)))
            for child in item:
                walk(child, depth + 1)
        elif type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError('INVALID_JSON_KEY')
            try:
                keys = sorted(item, key=lambda key: key.encode('utf-8'))
            except UnicodeError:
                raise ValueError('INVALID_UNICODE') from None
            emit(b'o' + struct.pack('>I', len(keys)))
            for key in keys:
                string(key)
                walk(item[key], depth + 1)
        else:
            raise ValueError('INVALID_JSON_VALUE')

    walk(value)
    return {'encoding': ENCODING, 'sha256': hashlib.sha256(b''.join(chunks)).hexdigest()}
