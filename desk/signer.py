"""Signer: the two keys the service itself holds, behind a scope policy.

The keyfile is JSON encrypted with XSalsa20-Poly1305 (PyNaCl SecretBox) under an Argon2id-derived
key from DESK_SIGNER_PASSPHRASE. It holds 32-byte seeds with fixed scopes:

  log     an ed25519 key that signs every event in the log, so the log's authorship is verifiable
  vault   a symmetric key (the seed bytes) that seals private ticket bodies and attachments at rest

What is NOT here, ever: anything that can move funds. Payouts are a member resolution in the DAO
harness; the desk only prepares the list. Reporters' keys never leave their browser.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from nacl import pwhash, secret, utils

from xe.keys import KeyPair

SCOPES = {
    "log": {"event.sign"},
    "vault": {"vault.seal", "vault.open"},
}
DEFAULT_KEYS = ("log", "vault")


class SignerError(RuntimeError):
    pass


@dataclass
class KeyInfo:
    name: str
    public_key: str
    address: str
    scopes: list[str]


def _kdf(passphrase: str, salt: bytes) -> bytes:
    return pwhash.argon2id.kdf(
        secret.SecretBox.KEY_SIZE,
        passphrase.encode("utf-8"),
        salt,
        opslimit=pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=pwhash.argon2id.MEMLIMIT_MODERATE,
    )


def encrypt_keyfile(contents: dict, passphrase: str) -> dict:
    salt = utils.random(pwhash.argon2id.SALTBYTES)
    box = secret.SecretBox(_kdf(passphrase, salt))
    ct = box.encrypt(json.dumps(contents).encode("utf-8"))
    return {"version": 1, "kdf": "argon2id", "salt": salt.hex(), "ciphertext": ct.hex()}


def decrypt_keyfile(blob: dict, passphrase: str) -> dict:
    box = secret.SecretBox(_kdf(passphrase, bytes.fromhex(blob["salt"])))
    try:
        pt = box.decrypt(bytes.fromhex(blob["ciphertext"]))
    except Exception as e:  # nacl.exceptions.CryptoError
        raise SignerError("keyfile passphrase is wrong or the file is corrupt") from e
    return json.loads(pt.decode("utf-8"))


class Signer:
    def __init__(self, keys: dict[str, KeyPair], scopes: dict[str, set[str]]):
        self._keys = keys
        self._scopes = scopes

    # ---- construction ---------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path, passphrase: str) -> "Signer":
        if not path.exists():
            raise SignerError(f"signer keyfile not found at {path}; run `desk keys init`")
        if not passphrase:
            raise SignerError("DESK_SIGNER_PASSPHRASE is empty")
        blob = json.loads(path.read_text(encoding="utf-8"))
        contents = decrypt_keyfile(blob, passphrase)
        keys = {name: KeyPair.from_seed_hex(seed) for name, seed in contents["keys"].items()}
        scopes = {name: set(s) for name, s in contents.get("scopes", {}).items()}
        for name in keys:
            scopes.setdefault(name, set(SCOPES.get(name, set())))
        return cls(keys, scopes)

    @classmethod
    def empty(cls) -> "Signer":
        return cls({}, {})

    @staticmethod
    def init_keyfile(
        path: Path, passphrase: str, names: tuple[str, ...] = DEFAULT_KEYS
    ) -> dict[str, KeyInfo]:
        if path.exists():
            raise SignerError(
                f"{path} already exists; refusing to overwrite. Check it opens with `desk keys show`. "
                "If it must be replaced (only before anything is sealed), delete the file on the host "
                "(./secrets/signer.json) and run again."
            )
        if len(passphrase) < 12:
            raise SignerError("passphrase must be at least 12 characters")
        keys = {n: KeyPair.generate() for n in names}
        contents = {
            "keys": {n: kp.seed.hex() for n, kp in keys.items()},
            "scopes": {n: sorted(SCOPES.get(n, set())) for n in names},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(encrypt_keyfile(contents, passphrase), indent=1), encoding="utf-8")
        os.chmod(path, 0o600)
        return {n: KeyInfo(n, kp.pub_key_hex, kp.address, contents["scopes"][n]) for n, kp in keys.items()}

    @staticmethod
    def add_key(path: Path, passphrase: str, name: str, scopes: set[str] | None = None) -> KeyInfo:
        blob = json.loads(path.read_text(encoding="utf-8"))
        contents = decrypt_keyfile(blob, passphrase)
        if name in contents["keys"]:
            raise SignerError(f"key {name!r} already exists")
        kp = KeyPair.generate()
        contents["keys"][name] = kp.seed.hex()
        sc = sorted(scopes if scopes is not None else SCOPES.get(name, set()))
        contents.setdefault("scopes", {})[name] = sc
        path.write_text(json.dumps(encrypt_keyfile(contents, passphrase), indent=1), encoding="utf-8")
        return KeyInfo(name, kp.pub_key_hex, kp.address, sc)

    # ---- use ------------------------------------------------------------------------------

    def has(self, name: str) -> bool:
        return name in self._keys

    def info(self, name: str) -> KeyInfo:
        kp = self._require(name)
        return KeyInfo(name, kp.pub_key_hex, kp.address, sorted(self._scopes.get(name, set())))

    def infos(self) -> list[KeyInfo]:
        return [self.info(n) for n in sorted(self._keys)]

    def public_key(self, name: str) -> str:
        return self._require(name).pub_key_hex

    def keypair(self, name: str, scope: str) -> KeyPair:
        kp = self._require(name)
        if scope not in self._scopes.get(name, set()):
            raise SignerError(f"key {name!r} is not permitted scope {scope!r}")
        return kp

    def sign(self, name: str, scope: str, message: bytes) -> str:
        return self.keypair(name, scope).sign_hex(message)

    def secret(self, name: str, scope: str) -> bytes:
        """The raw 32 bytes of a key, for symmetric use (the vault). Policy-checked like `sign`."""
        return self.keypair(name, scope).seed

    def _require(self, name: str) -> KeyPair:
        kp = self._keys.get(name)
        if kp is None:
            raise SignerError(f"no key named {name!r} in signer")
        return kp
