# Ticketer — Card Client (mock)

Mock socket client that plays the role of the **fare payment card** in a contactless
fare payment ("tap to pay") process.

The card authenticates itself to the gate/terminal using a **challenge–response
handshake over SSH-key cryptography**: it announces its public key, signs a
random 16-byte nonce returned by the terminal, and receives back an `OK` / `FAIL`
status.

> This is the **client** half of the project. The [terminal/gate](https://github.com/bgnacinski/conductor-ticketer) server listens on `localhost:2137`.

---

## Requirements

| Tool       | Version used | Notes                                       |
| ---------- | ------------ | ------------------------------------------- |
| Python     | 3.14+        | Only the standard library + `cryptography`   |
| OpenSSH    | 10.x+        | `ssh-keygen` is used to create the card keys |
| `pip`      | —            | Installed inside the project virtualenv      |

---

## Project layout

```
client/
├── main.py                 # the mock card client
├── requirements.txt        # pinned dependencies
├── crypto/                 # generated at runtime, git-ignored
│   ├── card_key            # Ed25519 / RSA2048 / ECDSA256 private key (OpenSSH format)
│   ├── card_key.pub        # matching public key
└── .venv/                  # local virtualenv, git-ignored
```

---

## How to run

### 1. SSH key pair setup

The `crypto/` directory is **git-ignored** (it holds private key material), so
every fresh clone must generate its own card key pair.

```bash
cd client
mkdir -p crypto

# Ed25519 key pair: private key -> crypto/card_key, public key -> crypto/card_key.pub
ssh-keygen -t ed25519 -f crypto/card_key -C "card@ticketer" -N ""
```

The private key is stored in **OpenSSH format** and is loaded by the client with
`serialization.load_ssh_private_key()`, so an OpenSSH-compatible key is required.

### 2. Installing the packages

```bash
# create the virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install the dependencies
pip install -r requirements.txt
```

### 3. Running the  client

From the **project root** (the client resolves `crypto/card_key`
relative to the current working directory):

```bash
source .venv/bin/activate
python main.py
```

On a successful handshake the client prints:

```
[*] Status: OK
```

On a rejected signature it prints:

```
[*] Status: FAIL
```

---

## Protocol

The handshake is a plain TCP exchange over `localhost:2137`:

```latex
Card                                        Terminal
 |                                              |
 |--- SSH public key (card_key.pub) ----------->|   authenticate the card
 |                                              |
 |<-- 16-byte random nonce (challenge) ---------|   prove possession of the key
 |                                              |
 |--- Ed25519 signature over the nonce -------->|   sign the challenge
 |                                              |
 |<-- "OK" / "FAIL" ----------------------------|   result
```

Steps in `main.py`:

1. Load the Ed25519 private key from `crypto/card_key` and the public key from
   `crypto/card_key.pub`.
2. Connect to `localhost:2137` and send the public key.
3. Receive the 16-byte nonce; abort if the length is wrong.
4. Sign the nonce with the private key and send the signature.
5. Read and print the terminal's response.

---

## Troubleshooting

| Symptom                                                    | Fix                                                                 |
| ---------------------------------------------------------- | ------------------------------------------------------------------- |
| `FileNotFoundError: crypto/card_key`                       | Run from the `client/` directory and complete the key setup.        |
| `Connection refused`                                       | Pretty self-explanatory - Server may not be running     |
| `Received challenge is not 16 bytes long`                  | A different service is listening on port `2137`.                    |
| `Permission denied` on `crypto/card_key`                   | Fix the mode with `chmod 600 crypto/card_key`.                      |
| `ValueError: Invalid key` / `not a private key`            | The key is not in OpenSSH format — regenerate it with `ssh-keygen`. |

---

## License

[LICENSE](LICENSE).
