from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


class HTTPServerEncryptedClass:
    def __init__(self):
        rsa_key = RSA.generate(2048)
        self.rsa_private_key = rsa_key.export_key()
        self.rsa_public_key = rsa_key.publickey().export_key()
        self.aes_key = None
    def rsa_encrypt(self, data):
        cipher_rsa = PKCS1_OAEP.new(RSA.import_key(self.rsa_public_key))
        return cipher_rsa.encrypt(data)
    def rsa_decrypt(self, data):
        cipher_rsa = PKCS1_OAEP.new(RSA.import_key(self.rsa_private_key))
        return cipher_rsa.decrypt(data)
    def set_aes_key(self, aes_key, iv):
        assert self.aes_key == None
        self.aes_key = aes_key
        self.aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv=iv)
        self.aes_decipher = AES.new(self.aes_key, AES.MODE_CBC, iv=iv)
    def aes_encrypt(self, data):
        ciphertext = self.aes_cipher.encrypt(pad(data, AES.block_size))
        return ciphertext
    def aes_decrypt(self, data):
        decrypted_message = unpad(self.aes_decipher.decrypt(data), AES.block_size)
        return decrypted_message
    def get_rsa_public_key(self):
        return self.rsa_public_key
