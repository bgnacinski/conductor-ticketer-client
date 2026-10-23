import socket
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

CHALL_SIZE = 16

with open("crypto/card_key", "rb") as card_key:
    priv_key = serialization.load_ssh_private_key(card_key.read(), None)

with open("crypto/card_key-cert.pub", "rb") as cert_file:
    cert = cert_file.read()


def sign_nonce(priv_key: serialization.SSHPrivateKeyTypes, nonce: bytes) -> bytes:
    """Sign the gate's challenge with the algorithm matching the card key."""
    if isinstance(priv_key, ed25519.Ed25519PrivateKey):
        return priv_key.sign(nonce)

    if isinstance(priv_key, ec.EllipticCurvePrivateKey):
        if priv_key.key_size <= 256:
            hash_algo = hashes.SHA256()
        elif priv_key.key_size <= 384:
            hash_algo = hashes.SHA384()
        else:
            hash_algo = hashes.SHA512()

        return priv_key.sign(nonce, ec.ECDSA(hash_algo))

    if isinstance(priv_key, rsa.RSAPrivateKey):
        return priv_key.sign(nonce, padding.PKCS1v15(), hashes.SHA512())

    raise TypeError(f"[!] Unsupported private key type: {type(priv_key).__name__}")


def attempt_access(conn: socket.socket):
    global cert

    conn.send(cert)

    try:
        response = conn.recv(CHALL_SIZE)
        if response in [b"INVALID_CERT", b"KEY_NOT_SECURE"]:
            print("[!] Status: ", response.decode())
            return

        elif len(response) != CHALL_SIZE:
            raise ValueError(f"[!] Received challenge is not {CHALL_SIZE} bytes long")

    except ConnectionError:
        print("[!] Connection closed!")
        return

    signature = sign_nonce(priv_key, response)
    conn.sendall(signature)

    try:
        response = conn.recv(1024)
        print(f"[*] Status: {response.decode()}")
    except ConnectionError:
        print("[!] Connection closed!")
        return


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 2137))
attempt_access(sock)
