from base64 import b64encode, b64decode
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import AES_KEY_DEFAULT, AES_IV_DEFAULT


class APIEncryption:
    def __init__(self):
        self.resetEncryption()

    def resetEncryption(self):
        self.aes_key = AES_KEY_DEFAULT   # must be 16/24/32 bytes
        self.aes_iv = AES_IV_DEFAULT     # must be 16 bytes
        self._token = ""                 # ensure defined

    async def _pad(self, data: bytes) -> bytes:
        """Manual zero padding to 16-byte blocks (matches your NoPadding approach)."""
        block_size = 16
        pad_len = (-len(data)) % block_size
        return data if pad_len == 0 else data + (b"\x00" * pad_len)

    async def _unpad(self, data: bytes) -> bytes:
        """Strip trailing nulls (⚠️ be aware this can lose intentional trailing zeros)."""
        return data.rstrip(b"\x00")

    async def encrypt(self, plain_text: str) -> str:
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_iv))
        encryptor = cipher.encryptor()
        padded = await self._pad(plain_text.encode("utf-8"))
        ct = encryptor.update(padded) + encryptor.finalize()
        return b64encode(ct).decode("utf-8")

    async def decrypt(self, encrypted_text: str) -> str:
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_iv))
        decryptor = cipher.decryptor()
        raw = b64decode(encrypted_text.replace(" ", "+"))
        pt_padded = decryptor.update(raw) + decryptor.finalize()
        pt = await self._unpad(pt_padded)
        return pt.decode("utf-8")

    async def _get_timestamp(self) -> str:
        return format(time.time(), ".6f")  # seconds with 6 decimal places

    async def getToken(self) -> str:
        return await self.encrypt(self._token + "@" + await self._get_timestamp())

    async def decodeLoginToken(self, login_token: str):
        self.resetEncryption()

        decrypted = await self.decrypt(login_token)
        parts = decrypted.split("@")

        if len(parts) >= 1:
            self._token = parts[0]
        if len(parts) >= 2:
            self.userid = parts[1]
            self.uid = await self.encrypt(parts[1])
        if len(parts) >= 3:
            self.aes_key = parts[2].encode()  # ensure 16/24/32 bytes
        if len(parts) >= 4:
            self.aes_iv = parts[3].encode()   # ensure 16 bytes
