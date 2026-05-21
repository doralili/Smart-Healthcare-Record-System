import base64
import json
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM #AESGCM为AES-GCM加密算法的一种

from app.core.config import settings


NONCE_SIZE = 12


class MedicalRecordCryptoError(Exception):
    pass

#加载验证密钥
def _load_key() -> bytes:
    try:
        key = base64.b64decode(settings.medical_record_key)
    except Exception as exc:
        raise MedicalRecordCryptoError("Invalid MEDICAL_RECORD_KEY format") from exc

    if len(key) != 32:
        raise MedicalRecordCryptoError("MEDICAL_RECORD_KEY must decode to 32 bytes")

    return key

#实现输入：医疗记录字典 → 输出：(加密数据, 随机数)
def encrypt_record_json(record: dict) -> tuple[str, str]:
    key = _load_key()
    nonce = secrets.token_bytes(NONCE_SIZE)  #解密病例

    plaintext = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    encrypted_data = base64.b64encode(ciphertext).decode("ascii")
    nonce_text = base64.b64encode(nonce).decode("ascii")

    return encrypted_data, nonce_text


def decrypt_record_json(encrypted_data: str, nonce: str) -> dict:
    key = _load_key()

    try:
        ciphertext = base64.b64decode(encrypted_data)
        nonce_bytes = base64.b64decode(nonce)
    except Exception as exc:
        raise MedicalRecordCryptoError("Invalid encrypted medical record encoding") from exc

    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext, None)
    except InvalidTag as exc:
        raise MedicalRecordCryptoError("Encrypted medical record was modified or key is wrong") from exc

    try:
        record = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise MedicalRecordCryptoError("Decrypted medical record is not valid JSON") from exc

    if not isinstance(record, dict):
        raise MedicalRecordCryptoError("Decrypted medical record must be a JSON object")

    return record


'''
从 .env 读取 MEDICAL_RECORD_KEY
把病历 dict 转成 JSON
用 AES-GCM 加密
返回encrypted_data, nonce
解密时再把它们还原成原来的dict
'''