"""Full .pts decrypt pipeline: decryptSM(inner_xor+CAST256-EAX) -> outer_xor -> qUncompress (x2) -> XML"""
import os
import sys, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cast256 import CAST256
from eax import eax_decrypt

KEY = bytes([0x12]*16)
NONCE = bytes([0xfe]*16)

def inner_xor_decrypt(buf):
    n = len(buf)
    out = bytearray(n)
    for i in range(n):
        out[i] = buf[n-1-i] ^ (((1 - i) * n) & 0xFF)
    return bytes(out)

def outer_xor(buf):
    n = len(buf)
    out = bytearray(n)
    for i in range(n):
        k = (n - i) & 0xFF if i % 2 == 0 else (n + i) & 0xFF
        out[i] = buf[i] ^ k
    return bytes(out)

def qUncompress(buf):
    # Qt format: 4-byte BE expected size + zlib stream
    if len(buf) < 4:
        return b''
    expected = struct.unpack('>I', buf[:4])[0]
    return zlib.decompress(buf[4:])

def decrypt_pts(path):
    raw = open(path, 'rb').read()
    print(f"File: {path}  size={len(raw)}  first16={raw[:16].hex()}")

    cast = CAST256(KEY)
    enc = cast.encrypt

    step1 = inner_xor_decrypt(raw)
    pt, tag_ok, exp = eax_decrypt(enc, NONCE, step1)
    print(f"  CAST256-EAX decrypt: tag_ok={tag_ok}, out_size={len(pt)}")
    print(f"  decrypted first 16: {pt[:16].hex()}")

    o1 = outer_xor(pt)
    print(f"  after outer_xor #1, first 8: {o1[:8].hex()}  (expect 4-byte size then 0x78 zlib)")
    print(f"  byte[4]=0x{o1[4]:02x} (0x78 = zlib OK)")
    try:
        u1 = qUncompress(o1)
        print(f"  qUncompress #1 OK: {len(u1)} bytes, first 16: {u1[:16].hex()}")
    except Exception as e:
        print(f"  qUncompress #1 FAILED: {e}")
        return None

    o2 = outer_xor(u1)
    print(f"  after outer_xor #2, byte[4]=0x{o2[4]:02x}")
    try:
        u2 = qUncompress(o2)
        print(f"  qUncompress #2 OK: {len(u2)} bytes")
    except Exception as e:
        print(f"  qUncompress #2 FAILED: {e}")
        # maybe only one round needed
        print(f"  u1 looks like XML? first 80: {u1[:80]}")
        return u1
    print(f"  === FINAL XML first 200 bytes ===\n{u2[:200]}")
    return u2

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else (sys.argv[1] if len(sys.argv)>1 else 'sample.pts')
    result = decrypt_pts(path)
    if result:
        out = path + '.xml'
        open(out, 'wb').write(result)
        print(f"\nWrote {len(result)} bytes to {out}")
