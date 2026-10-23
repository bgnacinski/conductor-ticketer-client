# Ticketer — Card Client (mock)

Mock socket client that plays the role of the **fare payment card** in a contactless
fare payment ("tap to pay") process.

The card authenticates itself to the gate/terminal by presenting an **SSH
certificate** issued by the gate's CA. The gate verifies the certificate (CA
signature and validity window) and the card's public key algorithm, then sends a
random 16-byte nonce that the card signs with its private key. The gate answers
with an `OK` / `FAIL` status.

The card key can be **Ed25519**, **ECDSA** (P-256/384/521) or **RSA** (≥ 2048
bits); the client signs the challenge with whichever algorithm the loaded key
uses.

> This is the **client** half of the project. The [terminal/gate](https://github.com/bgnacinski/conductor-ticketer) server listens on `localhost:2137`.

---

## Requirements

| Tool       | Version used | Notes                                         |
| ---------- | ------------ | --------------------------------------------- |
| Python     | 3.14+        | Only the standard library + `cryptography`     |
| OpenSSH    | 10.x+        | `ssh-keygen` creates and signs the card cert   |
| `pip`      | —            | Installed inside the project virtualenv        |

---

## Project layout

```
client/
├── main.py                 # the mock card client
├── requirements.txt        # pinned dependencies
├── crypto/                 # generated at runtime, git-ignored
│   ├── card_key            # private key (OpenSSH format)
│   ├── card_key.pub        # matching public key (input for signing)
│   └── card_key-cert.pub   # CA-signed certificate — this is what gets sent
└── .venv/                  # local virtualenv, git-ignored
```

The client reads **`crypto/card_key`** (private key) and
**`crypto/card_key-cert.pub`** (certificate). `card_key.pub` is only needed as the
input for signing the certificate.

---

## How to run

### 1. SSH key pair setup

The `crypto/` directory is **git-ignored** (it holds private key material), so
every fresh clone must generate its own card key pair and certificate.

```bash
# from the repository root (the client/ directory)
mkdir -p crypto

# pick one:
# Ed25519
ssh-keygen -t ed25519 -f crypto/card_key -C "card@ticketer" -N ""
# ECDSA P-256
ssh-keygen -t ecdsa -b 256 -f crypto/card_key -C "card@ticketer" -N ""
# RSA 2048
ssh-keygen -t rsa -b 2048 -f crypto/card_key -C "card@ticketer" -N ""
```

This creates the private key at `crypto/card_key` and the public key at
`crypto/card_key.pub`.

Keep the private key readable only by you:

```bash
chmod 600 crypto/card_key
chmod 644 crypto/card_key.pub
```

Verify the pair:

```bash
ssh-keygen -y -f crypto/card_key      # derived public key
cat crypto/card_key.pub               # stored public key
```

The private key is stored in **OpenSSH format** and is loaded by the client with
`serialization.load_ssh_private_key()`, so an OpenSSH-compatible key is required.

The client signs the challenge with the algorithm matching the loaded key:
Ed25519 natively, ECDSA with SHA-256/384/512 chosen by curve size, and RSA with
PKCS#1 v1.5 + SHA-512. ECDSA curves of 384 and 521 bits and larger RSA keys also
work; keys weaker than the gate's minimums (RSA < 2048, ECDSA < 256) are rejected
with `KEY_NOT_SECURE`.

#### Sign the card key with the gate's CA

The client sends a **certificate**, not a bare public key, so signing the card key
is a required step. The certificate must be signed by the CA whose public key is
provisioned on the gate (`../server/crypto/ca_key.pub`), otherwise the gate
answers `INVALID_CERT`.

If the gate's CA key pair does not exist yet, create it in the server project
(this produces `server/crypto/ca_key` and `server/crypto/ca_key.pub`):

```bash
mkdir -p ../server/crypto
ssh-keygen -t ed25519 -f ../server/crypto/ca_key -C "gate-ca" -N ""
```

Then sign the card's public key:

```bash
ssh-keygen -s ../server/crypto/ca_key \
    -I CARD_12345 \
    -n gate-user \
    -V +52w \
    crypto/card_key.pub
```

This produces `crypto/card_key-cert.pub`. Inspect it with:

```bash
ssh-keygen -L -f crypto/card_key-cert.pub
```

Typical output:

```
Type: ssh-ed25519-cert-v01@openssh.com user certificate
Key ID: "CARD_12345"
Valid: from 2026-10-22T22:43:00 to 2027-10-21T22:44:24
Principals:
        gate-user
Signing CA: ED25519 SHA256:HS+W9QSH+qUp9I9JCjl9W1QkSfVALmN+bCoEIsPjcfc
```

* `-I CARD_12345` — key ID identifying the card.
* `-n gate-user` — principal the card authenticates as.
* `-V +52w` — validity window (one year). The gate rejects certificates outside
  this window with `INVALID_CERT`.

> ⚠️ Never commit `crypto/` — it contains private keys. Both projects ignore it in
> `.gitignore`.

### 2. Installing the packages

```bash
# still in the repository root
# create the virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install the dependencies
pip install -r requirements.txt
```

`requirements.txt` pins:

```
cffi==2.1.1
cryptography==50.0.2
pycparser==3.11
```

### 3. Starting the gate (server)

The card expects a gate on `localhost:2137`. The gate needs its CA public key at
`../server/crypto/ca_key.pub`. Start it first:

```bash
cd ../server
source .venv/bin/activate        # create the server venv the same way if missing
python3 main.py
```

### 4. Running the card client

From the **project root** of `client/` (the client resolves its `crypto/` files
relative to the current working directory):

```bash
cd ../client
source .venv/bin/activate
python main.py
```

On a successful handshake the client prints:

```
[*] Status: OK
```

If the gate rejects the certificate:

```
[!] Status:  INVALID_CERT
```

If the certificate is valid but the key is too weak or unsupported:

```
[!] Status:  KEY_NOT_SECURE
```

If the nonce signature does not verify:

```
[*] Status: FAIL
```

---

## Protocol

The handshake is a plain TCP exchange over `localhost:2137`:

```
Card                                          Gate
 |                                             |
 |--- CA-signed certificate (card_key-cert) -->|  parse certificate
 |                                             |  verify CA signature + validity window
 |                                             |  check public key algorithm
 |                                             |
 |<-- 16-byte random nonce (challenge) --------|  or INVALID_CERT / KEY_NOT_SECURE
 |                                             |
 |--- signature over the nonce (card_key) ---->|  verify proof of possession
 |                                             |
 |<-- "OK" / "FAIL" ---------------------------|  result
```

Steps in `main.py`:

1. Load the private key from `crypto/card_key` and the certificate from
   `crypto/card_key-cert.pub`.
2. Connect to `localhost:2137` and send the certificate.
3. Receive the reply:
   * `INVALID_CERT` / `KEY_NOT_SECURE` — print the status and stop.
   * anything that is not a 16-byte nonce — raise an error.
4. Sign the nonce with `sign_nonce()` — which selects the signature algorithm
   from the key type — and send the signature.
5. Read and print the gate's response (`OK` / `FAIL`).

### Accepted card key algorithms

The gate validates the certificate first, then enforces a minimum key strength.
Weak or unsupported keys are rejected with `KEY_NOT_SECURE` before a challenge is
issued. The client picks the matching signature algorithm from the loaded key.

| Algorithm | Requirement           | Gate | This client            |
| --------- | --------------------- | ---- | ---------------------- |
| Ed25519   | any key               | ✅    | ✅                      |
| ECDSA     | curve size ≥ 256 bits | ✅    | ✅ P-256 / P-384 / P-521 |
| RSA       | size ≥ 2048 bits      | ✅    | ✅                      |

The client signs with PKCS#1 v1.5 + SHA-512 for RSA, and with ECDSA/SHA-256,
SHA-384 or SHA-512 for 256-, 384- and 521-bit curves respectively — matching what
the gate verifies. Other key types (DSA, Ed448) are rejected by the gate as
`KEY_NOT_SECURE`; if one ever reaches the signing step, the client raises
`[!] Unsupported private key type: ...`.

---

## Troubleshooting

| Symptom                                                     | Cause / fix                                                                                                          |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `FileNotFoundError: crypto/card_key`                          | Run from `client/` and complete the key setup.                                                                        |
| `FileNotFoundError: crypto/card_key-cert.pub`                 | The certificate is missing — sign `card_key.pub` with the gate's CA (step 1).                                         |
| `Connection refused`                                          | Pretty self-explanatory — the gate may not be running.                                                                |
| `[!] Status:  INVALID_CERT`                                   | The certificate is not signed by the gate's CA, or the current date is outside its `-V` validity window.              |
| `[!] Status:  KEY_NOT_SECURE`                                 | The key algorithm is not accepted, or the key is too weak (RSA < 2048 bits, ECDSA < 256 bits).                        |
| `[*] Status: FAIL`                                            | The certificate and key were accepted, but the nonce signature did not verify.                                        |
| `Received challenge is not 16 bytes long`                     | The gate replied with something that is neither a 16-byte nonce nor a known status — check the gate log.              |
| `TypeError: [!] Unsupported private key type: ...`          | The loaded key type is not supported (DSA, Ed448, …). Regenerate it as Ed25519, ECDSA or RSA.                          |
| `[!] Connection closed!`                                      | The gate dropped the connection, usually while parsing a malformed certificate.                                       |
| `Permission denied` on `crypto/card_key`                      | Fix the mode with `chmod 600 crypto/card_key`.                                                                        |
| `ValueError: Invalid key` / `not a private key`               | The key is not in OpenSSH format — regenerate it with `ssh-keygen`.                                                   |

---

## License

[LICENSE](LICENSE).
