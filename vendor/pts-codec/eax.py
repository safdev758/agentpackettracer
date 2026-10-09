"""Generic EAX mode (Bellare-Rogaway-Wagner) over any 128-bit block cipher."""
import struct

def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def _dbl(block):
    # GF(2^128) doubling, big-endian, reduction poly 0x87
    n = int.from_bytes(block, 'big')
    n2 = (n << 1) & ((1 << 128) - 1)
    if n & (1 << 127):
        n2 ^= 0x87
    return n2.to_bytes(16, 'big')

def cmac(enc, msg):
    """CMAC over msg using block-encrypt fn enc (16-byte block in/out)."""
    L = enc(bytes(16))
    K1 = _dbl(L)
    K2 = _dbl(K1)
    if len(msg) == 0:
        # single padded incomplete block
        last = bytes([0x80]) + bytes(15)
        last = _xor(last, K2)
        return enc(last)
    # split into 16-byte blocks
    blocks = [msg[i:i+16] for i in range(0, len(msg), 16)]
    X = bytes(16)
    for blk in blocks[:-1]:
        X = enc(_xor(X, blk))
    last = blocks[-1]
    if len(last) == 16:
        last = _xor(last, K1)
    else:
        last = last + bytes([0x80]) + bytes(15 - len(last))
        last = _xor(last, K2)
    return enc(_xor(X, last))

def _omac(enc, t, msg):
    # OMAC^t = CMAC(<t>_128 || msg)
    prefix = t.to_bytes(16, 'big')
    return cmac(enc, prefix + msg)

def _ctr(enc, ctr0, data):
    out = bytearray()
    ctr = int.from_bytes(ctr0, 'big')
    for i in range(0, len(data), 16):
        ks = enc((ctr & ((1<<128)-1)).to_bytes(16, 'big'))
        chunk = data[i:i+16]
        out += _xor(chunk, ks[:len(chunk)])
        ctr += 1
    return bytes(out)

def eax_decrypt(enc, nonce, ciphertext_with_tag, header=b'', tag_at_end=True):
    if tag_at_end:
        ct, tag = ciphertext_with_tag[:-16], ciphertext_with_tag[-16:]
    else:
        tag, ct = ciphertext_with_tag[:16], ciphertext_with_tag[16:]
    N = _omac(enc, 0, nonce)
    H = _omac(enc, 1, header)
    Cm = _omac(enc, 2, ct)
    expected_tag = _xor(_xor(N, Cm), H)
    pt = _ctr(enc, N, ct)
    return pt, (expected_tag == tag), expected_tag

def eax_encrypt(enc, nonce, plaintext, header=b''):
    N = _omac(enc, 0, nonce)
    H = _omac(enc, 1, header)
    C = _ctr(enc, N, plaintext)
    Cm = _omac(enc, 2, C)
    tag = _xor(_xor(N, Cm), H)
    return C + tag

if __name__ == '__main__':
    # Validate generic EAX logic against PyCryptodome EAX using AES as the block cipher
    from Crypto.Cipher import AES
    key = bytes(range(16))
    nonce = bytes([0xaa]*16)
    pt = b"The quick brown fox jumps over the lazy dog!! 1234567890 padding"
    aes = AES.new(key, AES.MODE_ECB)
    enc = lambda b: aes.encrypt(b)
    mine = eax_encrypt(enc, nonce, pt)
    ref = AES.new(key, AES.MODE_EAX, nonce=nonce, mac_len=16)
    rc, rt = ref.encrypt_and_digest(pt)
    print("EAX encrypt matches PyCryptodome:", mine == rc + rt)
    # decrypt round-trip
    dpt, ok, _ = eax_decrypt(enc, nonce, mine)
    print("EAX decrypt round-trip:", dpt == pt, "tag ok:", ok)
