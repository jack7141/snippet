import base64
import json
from urllib.parse import unquote

from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class SeedCBC(object):

    def __init__(self, key, iv, **kwargs):
        self.key = key
        self.iv = iv

        self._init_seed_key()
        self._init_iv()

    def _init_iv(self):
        """
        initialization_vector키를 가져옵니다.

        문자열을 입력받아 SHA256 해쉬를 한 뒤
        16~32번째 문자열을 초기화 벡터값으로 사용합니다.
        """
        iv = self.iv
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(str.encode(iv))
        self._iv = digest.finalize()[16:32]

    def _init_seed_key(self):
        """
        seed 알고리즘에 사용되는 키를 가져옵니다.

        자열을 입력받아 SHA256 해쉬를 한 뒤
        0~16번째 문자열을 초기화 벡터값으로 사용합니다.
        """
        key = self.key
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(str.encode(key))
        self._key = digest.finalize()[0:16]

    def encrypt(self, plaintext, encoding='utf-8'):
        """
        base64로 암호호된 문자열을 가져옵니다.
        """
        key = self._key
        iv = self._iv

        cipher = Cipher(algorithms.SEED(key), mode=modes.CBC(iv), backend=default_backend())
        encoded_message = str.encode(plaintext)
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(encoded_message)
        padded_data += padder.finalize()
        ct = encryptor.update(padded_data) + encryptor.finalize()

        return str(base64.b64encode(ct), encoding)

    def decrypt(self, base64_message, decoding='utf-8', to_json=False):
        """
        base64로 암호호된 문자열을 복호화 합니다.
        """
        key = self._key
        iv = self._iv

        cipher = Cipher(algorithms.SEED(key), mode=modes.CBC(iv), backend=default_backend())
        encrypt_message = base64.b64decode(base64_message)
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(encrypt_message) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        pt = unpadder.update(plaintext) + unpadder.finalize()
        decrypted = unquote(bytes.decode(pt, decoding))

        if to_json:
            return json.loads(decrypted)
        return decrypted


def initialization_vector(iv):
    """
    initialization_vector키를 가져옵니다.

    문자열을 입력받아 SHA256 해쉬를 한 뒤
    16~32번째 문자열을 초기화 벡터값으로 사용합니다.

    :param iv: 초기화 벡터를 생성위한 문자열
    :return:
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(str.encode(iv))
    return digest.finalize()[16:32]


def seed_key(key):
    """
    seed 알고리즘에 사용되는 키를 가져옵니다.

    자열을 입력받아 SHA256 해쉬를 한 뒤
    0~16번째 문자열을 초기화 벡터값으로 사용합니다.

    :param key: key값으로 사용될 문자열
    :return:
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(str.encode(key))
    return digest.finalize()[0:16]


def seed_encrypt_message(plaintext, key, iv):
    """
    base64로 암호호된 문자열을 가져옵니다.

    :param plaintext: 평문
    :param key: 암호화에 쓰일 키
    :param iv: 초기화 벡터
    :return:
    """
    cipher = Cipher(algorithms.SEED(key), mode=modes.CBC(iv), backend=default_backend())
    encoded_message = str.encode(plaintext)
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(encoded_message)
    padded_data += padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return str(base64.b64encode(ct), 'utf-8')


def seed_decrypt_message(base64_message, key, iv):
    """
    base64로 암호호된 문자열을 복호화 합니다.

    :param base64_message:
    :param key: 복호화에 쓰일 키
    :param iv: 암호화에 쓰였던 초기화 벡터
    :return:
    """
    cipher = Cipher(algorithms.SEED(key), mode=modes.CBC(iv), backend=default_backend())
    encrypt_message = base64.b64decode(base64_message)
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(encrypt_message) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    pt = unpadder.update(plaintext) + unpadder.finalize()
    return bytes.decode(pt, 'utf-8')
