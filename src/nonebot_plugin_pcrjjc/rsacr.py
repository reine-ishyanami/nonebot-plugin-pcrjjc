import base64

from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Crypto.PublicKey import RSA


# 加密
def rsa_create(message, public_key):
    rsa_key = RSA.importKey(public_key)
    cipher = Cipher_pkcs1_v1_5.new(rsa_key)  # 创建用于执行pkcs1_v1_5加密或解密的密码
    cipher_text = base64.b64encode(cipher.encrypt(message.encode('utf-8')))
    text = cipher_text.decode('utf-8')
    return text
