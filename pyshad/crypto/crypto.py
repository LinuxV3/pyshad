import re
import json
import base64
import string
import secrets
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
from Crypto.Util.Padding import pad, unpad
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from string import ascii_lowercase, ascii_uppercase



def save_private(private):
    s = open("my_private.txt", 'wt')
    s.write(private)
    s.close()


class Crypto:
    AES_IV = b'\x00' * 16

    @staticmethod
    def decode_auth(auth: str) -> str:
        """
        Decode an auth string by applying character substitutions.

        Args:
            auth (str): The input auth string.

        Returns:
            str: The decoded auth string.
        """
        result_list, digits = [], '0123456789'
        translation_table_lower = str.maketrans(
            ascii_lowercase,
            ''.join([chr(((32 - (ord(c) - 97)) % 26) + 97) for c in ascii_lowercase])
        )
        translation_table_upper = str.maketrans(
            ascii_uppercase,
            ''.join([chr(((29 - (ord(c) - 65)) % 26) + 65) for c in ascii_uppercase])
        )

        for char in auth:
            if char in ascii_lowercase:
                result_list.append(char.translate(translation_table_lower))
            elif char in ascii_uppercase:
                result_list.append(char.translate(translation_table_upper))
            elif char in digits:
                result_list.append(chr(((13 - (ord(char) - 48)) % 10) + 48))
            else:
                result_list.append(char)

        return ''.join(result_list)

    @classmethod
    def passphrase(cls, auth):
        """
        Generate a passphrase from an auth string.

        Args:
            auth (str): The input auth string.

        Returns:
            str: The generated passphrase.
        """
        if len(auth) != 32:
            raise ValueError('auth length should be 32 digits')

        result_list = []
        chunks = re.findall(r'\S{8}', auth)
        for character in (chunks[2] + chunks[0] + chunks[3] + chunks[1]):
            result_list.append(chr(((ord(character) - 97 + 9) % 26) + 97))
        return ''.join(result_list)

    @classmethod
    def secret(cls, length):
        """
        Generate a random secret of the given length.

        Args:
            length (int): Length of the secret.

        Returns:
            str: The generated secret.
        """
        return ''.join(secrets.choice(string.ascii_lowercase)
                       for _ in range(length))

    @classmethod
    def decrypt(cls, data, key):
        """
        Decrypt data using AES encryption.

        Args:
            data (str): The encrypted data.
            key (str): The encryption key.

        Returns:
            dict: The decrypted data as a dictionary.
        """
        save_private(key)
        aes = AES.new(key.encode(), AES.MODE_CBC, cls.AES_IV)
        dec = aes.decrypt(base64.urlsafe_b64decode(data.encode('UTF-8')))
        return json.loads(unpad(dec, AES.block_size).decode('UTF-8'))

    @classmethod
    def encrypt(cls, data: str, key: str):
        """
        Encrypt data using AES encryption.

        Args:
            data (str or dict): The data to be encrypted.
            key (str): The encryption key.

        Returns:
            str: The encrypted data as a string.
        """
        if isinstance(data, dict):
            data = json.dumps(data)
        raw = pad(data.encode('UTF-8'), AES.block_size)
        aes = AES.new(key.encode(), AES.MODE_CBC, cls.AES_IV)
        return base64.b64encode(aes.encrypt(raw)).decode('UTF-8')

    @staticmethod
    def sign(pkcs1_15: "pkcs1_15.new", data: str) -> str:
        """
        Sign data using an RSA private key.

        Args:
            private_key (str): The RSA private key.
            data (str): The data to be signed.

        Returns:
            str: The base64-encoded signature.
        """
        #key = RSA.import_key(private_key.encode('utf-8'))
        signature = pkcs1_15.sign(SHA256.new(data.encode('utf-8')))
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def makeSignFromData(data_enc: str, private_key):
        sha_data = SHA256.new(data_enc.encode("utf-8"))
        try:
            keypair = RSA.import_key(private_key.encode("utf-8"))
        except ValueError:
            private_key = eval(base64.b64decode(private_key))['d']
            keypair = RSA.import_key(private_key.encode("utf-8"))
        signature = pkcs1_15.new(keypair).sign(sha_data)
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def create_keys() -> tuple:
        """
        Generate RSA public and private keys.

        Returns:
            tuple: A tuple containing the base64-encoded public key and the private key.
        """
        keys = RSA.generate(1024)
        public_key = Crypto.decode_auth(base64.b64encode(keys.publickey().export_key()).decode('utf-8'))
        private_key = keys.export_key().decode('utf-8')
        return public_key, private_key

    @staticmethod
    def decrypt_RSA_OAEP(private_key: str, data: str):
        """
        Decrypt data using RSA OAEP encryption.

        Args:
            private_key (str): The RSA private key.
            data (str): The encrypted data.

        Returns:
            str: The decrypted data as a string.
        """
        key = RSA.import_key(private_key.encode('utf-8'))
        return PKCS1_OAEP.new(key).decrypt(base64.b64decode(data)).decode('utf-8')






class Crypto2:
    # Coded by <github.com/sajjadsoleimani>
    def __init__(self, auth: str, private_key: str = None):
        self.auth = auth
        self.key = bytearray(self.secret(auth), "UTF-8")
        self.iv = bytearray.fromhex('0' * 32)
        if private_key:
            self.keypair = RSA.import_key(private_key.encode("utf-8"))

    def replaceCharAt(self, e, t, i):
        return e[0:t] + i + e[t + len(i):]

    def changeAuthType(auth_enc):
        n = ""
        lowercase = "abcdefghijklmnopqrstuvwxyz"
        uppercase = lowercase.upper()
        digits = "0123456789"
        for s in auth_enc:
            if s in lowercase:
                n += chr(((32 - (ord(s) - 97)) % 26) + 97)
            elif s in uppercase:
                n += chr(((29 - (ord(s) - 65)) % 26) + 65)
            elif s in digits:
                n += chr(((13 - (ord(s) - 48)) % 10) + 48)
            else:
                n += s
        return n

    def secret(self, e):
        t = e[0:8]
        i = e[8:16]
        n = e[16:24] + t + e[24:32] + i
        s = 0
        while s < len(n):
            e = n[s]
            if e >= '0' and e <= '9':
                t = chr((ord(e[0]) - ord('0') + 5) % 10 + ord('0'))
                n = self.replaceCharAt(n, s, t)
            else:
                t = chr((ord(e[0]) - ord('a') + 9) % 26 + ord('a'))
                n = self.replaceCharAt(n, s, t)
            s += 1
        return n

    def encrypt(self, text):
        raw = pad(text.encode('UTF-8'), AES.block_size)
        aes = AES.new(self.key, AES.MODE_CBC, self.iv)
        enc = aes.encrypt(raw)
        result = base64.b64encode(enc).decode('UTF-8')
        return result

    def decrypt(self, text):
        aes = AES.new(self.key, AES.MODE_CBC, self.iv)
        dec = aes.decrypt(base64.urlsafe_b64decode(text.encode('UTF-8')))
        result = unpad(dec, AES.block_size).decode('UTF-8')
        return result

    def makeSignFromData(self, data_enc: str):
        sha_data = SHA256.new(data_enc.encode("utf-8"))
        signature = pkcs1_15.new(self.keypair).sign(sha_data)
        return base64.b64encode(signature).decode("utf-8")

    def decryptRsaOaep(private: str, data_enc: str):
        keyPair = RSA.import_key(private.encode("utf-8"))
        return PKCS1_OAEP.new(keyPair).decrypt(base64.b64decode(data_enc)).decode("utf-8")

    def rsaKeyGenerate():
        keyPair = RSA.generate(1024)
        public = Crypto2.changeAuthType(base64.b64encode(keyPair.publickey().export_key()).decode("utf-8"))
        private = keyPair.export_key().decode("utf-8")
        return public, private

from json import loads
from base64 import b64decode
key = "eyJ2ZXJzaW9uIjoiNiIsImQiOiItLS0tLUJFR0lOIFJTQSBQUklWQVRFIEtFWS0tLS0tXG5NSUlDV3dJQkFBS0JnUURQVWc3QUJIZVlxcTA1djQ5bVJzaGh0QWdIdjgra0c1WVVKZ2I5YVQvdmtBN0NRclkrXG5LblFMbTJ3UWI5a1daKzFUakFhNURRNUpESXR5M0R4K2poTDV5eXY2Z2xiYlVRTDUyL1hqVnBJaFluVkE3b3h0XG5mOU5Sc2FjcWpJdzFVY3I5YXNyMk94R1VWeDJuQ2Iremc4eCtHVDBFM09JajV6cFVqcVNjT0tLSFdRSURBUUFCXG5Bb0dBUm03eFZlanVuSzQzaGF2LzB0WnZVMG92aERwMUY2TExuUExDWXl0enJqYTUzT04vT0tXQm9VUGZOY0paXG45Vk8vZkNmUlRPTVRuRnVuc0pFRCtGYmFPT2VqZUJXSTdJOW5kY3hHUnJiTHJBQmprMjIxdXJNUW9OMjR1ODBmXG5UaWFHV1RyMkJwblBBRFFQMy9adVRxSTk5ZlI4a0xoR0ptdGZRK2NockhPZ2hZVUNRUUQvTU5xa3cvNm1ZTDQwXG5yU1crKzlOZ2JFM2ZKbmc1WFVudmFJektPTEptWk04TFE5cjB5VEpwYWphNklvT0pJSUVNVmx0NFRuM09aUEIrXG5OV2ZNT2VETEFrRUF6L3BZaHVjVkw2L1NPSmZrWExPOTJOVGF6dEFjK3RBVkY1N3dlZlVaYXNSTFE0UVpZUm13XG5odmR5eEp6NnpvWlJ0eTJ1Zi9GenNpTmpwVTFaTGI3bjZ3SkFQTDl6ZlArUE1pb2JmVXl1akoxRC8xTW80bk0wXG44V3JzdThvbW9ja0hadXFlZ3U3L1E0QlZ1TlJvL0x4VWxhTWdOVUNsZTZrcnQ2TTl3TDJUM1FEMkt3SkFWTzE3XG4vUXFjSWk3Ly8xQTNWb3VuZU1YaTNCVXI0RmZjWlJyb1JFVU1MZ2NlWE9HeW8yNGtJZGttS3BlWDY0SDZHSDAxXG5CdFlJVXJRVTJzbXRJdnNVSlFKQU9xOHVvS3VyWDZlcTJYLzlkMldXY0hPSUpCOVMwNWtjODlZa2NSTWpoMTU3XG51dmtNVXNWdnhCb0h0TUJpSFRjYXJnWlZKSU5vWG84RG5vUDhlY0lWdHc9PVxuLS0tLS1FTkQgUlNBIFBSSVZBVEUgS0VZLS0tLS0ifQ=="
auth = "xezkvfuwpdfrgooopvzzwkumueyyfpui"
key = loads(b64decode(key))['d']
c = Crypto2(auth=auth, private_key=key)

