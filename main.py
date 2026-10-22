import socket
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

CHALL_SIZE = 16

with open("crypto/card_key", "rb") as card_key:
    priv_key = serialization.load_ssh_private_key(card_key.read(), None, backend=ed25519)

with open("crypto/card_key.pub", "rb") as pubkey_file:
    pubkey = pubkey_file.read()

def attempt_access(conn: socket.socket):
    global pubkey
    global priv_key
        
    conn.send(pubkey)
    
    try:
        nonce = conn.recv(CHALL_SIZE)
        if len(nonce) != CHALL_SIZE:
            raise ValueError(f"[!] Received challenge is not {CHALL_SIZE} bytes long")
    except ConnectionError:
        print("[!] Connection closed!")
        return
        
    signature = priv_key.sign(nonce)
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