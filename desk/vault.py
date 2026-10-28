"""The vault: private ticket bodies and attachments, sealed at rest.

SecretBox (XSalsa20-Poly1305) under the `vault` key from the service keyfile. The ciphertext is
stored; the plaintext exists only in the response to a reader the authorisation layer has already
admitted, and that read is an event in the log. If the keyfile is absent the desk still runs, but
refuses to accept or open private content rather than storing it in the clear.
"""

from __future__ import annotations

from nacl import secret, utils

from .signer import Signer, SignerError


class VaultError(RuntimeError):
    pass


class Vault:
    def __init__(self, signer: Signer):
        self._signer = signer

    @property
    def available(self) -> bool:
        return self._signer.has("vault")

    def _box(self, scope: str) -> secret.SecretBox:
        try:
            return secret.SecretBox(self._signer.secret("vault", scope))
        except SignerError as e:
            raise VaultError("the vault key is not available; private content cannot be handled") from e

    def seal(self, plaintext: bytes) -> bytes:
        """nonce || ciphertext, as PyNaCl emits it."""
        return bytes(self._box("vault.seal").encrypt(plaintext, utils.random(secret.SecretBox.NONCE_SIZE)))

    def open(self, sealed: bytes) -> bytes:
        try:
            return bytes(self._box("vault.open").decrypt(sealed))
        except VaultError:
            raise
        except Exception as e:  # nacl.exceptions.CryptoError
            raise VaultError("sealed content did not open; wrong key or corrupt data") from e

    def seal_text(self, text: str) -> bytes:
        return self.seal(text.encode("utf-8"))

    def open_text(self, sealed: bytes) -> str:
        return self.open(sealed).decode("utf-8")
