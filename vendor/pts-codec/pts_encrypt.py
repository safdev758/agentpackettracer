"""Full .pts encrypt pipeline (inverse of decrypt):
XML -> qCompress -> outer_xor -> qCompress -> outer_xor -> EAX_encrypt -> inner_xor_encrypt -> file"""
import os
import sys, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cast256 import CAST256
from eax import eax_encrypt, eax_decrypt

KEY = bytes([0x12]*16)
NONCE = bytes([0xfe]*16)

def inner_xor_decrypt(buf):
    n = len(buf); out = bytearray(n)
    for i in range(n):
        out[i] = buf[n-1-i] ^ (((1 - i) * n) & 0xFF)
    return bytes(out)

def inner_xor_encrypt(buf):
    n = len(buf); out = bytearray(n)
    for i in range(n):
        out[n-1-i] = buf[i] ^ (((1 - i) * n) & 0xFF)
    return bytes(out)

def outer_xor(buf):
    n = len(buf); out = bytearray(n)
    for i in range(n):
        k = (n - i) & 0xFF if i % 2 == 0 else (n + i) & 0xFF
        out[i] = buf[i] ^ k
    return bytes(out)

def qCompress(data, level=-1):
    # Qt format: 4-byte BE uncompressed size + zlib stream
    return struct.pack('>I', len(data)) + zlib.compress(data, level if level>=0 else 6)

def qUncompress(buf):
    return zlib.decompress(buf[4:])

def encrypt_pts(xml_bytes):
    cast = CAST256(KEY)
    enc = cast.encrypt
    A = qCompress(xml_bytes)          # inverse of last qUncompress
    B = outer_xor(A)
    C = qCompress(B)
    D = outer_xor(C)
    E = eax_encrypt(enc, NONCE, D)    # ciphertext + 16-byte tag
    f = inner_xor_encrypt(E)
    return f

# ---- self-test sanity for the xor inverses ----
def _selftest_xors():
    import os
    for n in (1, 2, 15, 16, 17, 1000, 82248):
        x = bytes((i*37+11) & 0xFF for i in range(n))
        assert inner_xor_decrypt(inner_xor_encrypt(x)) == x, f"inner inverse fail n={n}"
        assert inner_xor_encrypt(inner_xor_decrypt(x)) == x, f"inner inverse2 fail n={n}"
        assert outer_xor(outer_xor(x)) == x, f"outer self-inverse fail n={n}"
    print("XOR inverse self-tests: PASS")

if __name__ == '__main__':
    _selftest_xors()
    # Round-trip test: take the decrypted XML, re-encrypt, decrypt again
    xml = open((sys.argv[1] if len(sys.argv)>1 else 'sample.xml'),'rb').read()
    print(f"Original XML: {len(xml)} bytes")
    reencrypted = encrypt_pts(xml)
    print(f"Re-encrypted .pts: {len(reencrypted)} bytes (original file was 82248)")
    open((sys.argv[2] if len(sys.argv)>2 else 'out.pts'),'wb').write(reencrypted)

    # Now decrypt it back
    cast = CAST256(KEY); enc = cast.encrypt
    s1 = inner_xor_decrypt(reencrypted)
    pt, tag_ok, _ = eax_decrypt(enc, NONCE, s1)
    print(f"  re-decrypt EAX tag_ok={tag_ok}")
    o1 = outer_xor(pt); u1 = qUncompress(o1)
    o2 = outer_xor(u1); u2 = qUncompress(o2)
    print(f"  round-trip XML matches original: {u2 == xml}")
