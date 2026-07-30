import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class CryptoEngine:
    KEY = b'638udh3829162018'
    IV = b'fedcba9876543210'

    @staticmethod
    def decrypt_appx(enc_str: str) -> str:
        """Decrypt AES-CBC encrypted URLs/links from Appx/Classx platforms."""
        if not enc_str:
            return ""
        try:
            raw_enc = base64.b64decode(enc_str.split(':')[0])
            if len(raw_enc) == 0:
                return ""
            cipher = AES.new(CryptoEngine.KEY, AES.MODE_CBC, CryptoEngine.IV)
            decrypted = unpad(cipher.decrypt(raw_enc), AES.block_size)
            return decrypted.decode('utf-8')
        except Exception:
            return enc_str

    @staticmethod
    def decode_base64(encoded_str: str) -> str:
        """Helper to safely decode Base64 strings."""
        try:
            return base64.b64decode(encoded_str).decode('utf-8')
        except Exception:
            return encoded_str