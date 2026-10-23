import socket
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

CHALL_SIZE = 16

with open("crypto/card_key", "rb") as card_key:
    priv_key = serialization.load_ssh_private_key(card_key.read(), None, backend=ed25519)

with open("crypto/card_key-cert.pub", "rb") as cert_file:
    cert = cert_file.read()

def attempt_access(conn: socket.socket):
    global cert
    global priv_key
        
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
    
    # różne argumenty dla różnych typów kluczy - to jest dobre tylko dla ed25519
    signature = priv_key.sign(response)
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