from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from base64 import b64encode, b64decode


class Aes(object):
    def __init__(self, key):
        self.key = key

    def encrypt(self, data: str) -> str:
        """
        :param data: plain text data
        :return: encrypted string data in base64
        """
        iv = get_random_bytes(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        enc = b64encode(iv + cipher.encrypt(pad(data.encode(), AES.block_size))).decode()
        return enc

    def decrypt(self, data: str) -> str:
        """
        :param data: encrypted data
        :return: decrypted string data
        """
        data = b64decode(data)
        cipher = AES.new(self.key, AES.MODE_CBC, data[:AES.block_size])
        dec = unpad(cipher.decrypt(data[AES.block_size:]), AES.block_size).decode()
        return dec