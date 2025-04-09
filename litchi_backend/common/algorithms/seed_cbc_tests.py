import json
from urllib.parse import unquote
from common.algorithms.seed_cbc import *

iv = initialization_vector("secretivkeys_")
key = seed_key("seedseedseedseedseed")

enc_data = seed_encrypt_message("test", key=key, iv=iv)

print(enc_data)

dec_data = unquote(seed_decrypt_message(enc_data, key=key, iv=iv))

try:
    print(json.loads(dec_data), type(json.loads(dec_data)))
except json.JSONDecodeError:
    print(dec_data, type(dec_data))
