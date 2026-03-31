"""
Claw Memory 加密模块 - Data Encryption
支持AES加密敏感数据（transcript、content）

注意：这是基础加密，用于防止数据泄露
完整GDPR合规需要更多功能（见memory_privacy.py）
"""
import base64
import hashlib
import os
from typing import Optional

# 是否启用加密
ENCRYPTION_ENABLED = True

# 密钥（实际应该从环境变量或密钥管理系统获取）
# 这里使用基于设备ID的派生密钥
def _get_encryption_key() -> bytes:
    """获取加密密钥（基于机器派生）"""
    # 使用MAC地址的MD5作为密钥（简单方案）
    import uuid
    mac = uuid.getnode()
    key_material = f"ClawMemory_{mac}_secure_key"
    return hashlib.sha256(key_material.encode()).digest()


def encrypt_text(plaintext: str) -> str:
    """
    加密文本
    
    Args:
        plaintext: 明文
        
    Returns:
        Base64编码的密文（包含IV）
    """
    if not ENCRYPTION_ENABLED or not plaintext:
        return plaintext
    
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        
        key = _get_encryption_key()
        iv = os.urandom(16)  # 16字节IV
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        
        # 组合 IV + 密文，然后Base64
        combined = iv + encrypted
        return base64.b64encode(combined).decode('utf-8')
        
    except ImportError:
        # 如果没有pycryptodome，使用简单XOR（不安全但可用）
        return _xor_encrypt(plaintext)
    except Exception as e:
        import logging
        logging.warning(f"Encryption failed: {e}")
        return plaintext


def decrypt_text(ciphertext: str) -> str:
    """
    解密文本
    
    Args:
        ciphertext: Base64编码的密文
        
    Returns:
        明文
    """
    if not ENCRYPTION_ENABLED or not ciphertext:
        return ciphertext
    
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        
        key = _get_encryption_key()
        
        # Base64解码
        combined = base64.b64decode(ciphertext.encode('utf-8'))
        
        # 分离IV和密文
        iv = combined[:16]
        encrypted = combined[16:]
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        unpadded = unpad(decrypted, AES.block_size)
        
        return unpadded.decode('utf-8')
        
    except ImportError:
        return _xor_decrypt(ciphertext)
    except Exception as e:
        import logging
        logging.warning(f"Decryption failed: {e}")
        return ciphertext


def _xor_encrypt(plaintext: str) -> str:
    """简单XOR加密（备用方案）"""
    key = _get_encryption_key()
    result = []
    for i, c in enumerate(plaintext):
        key_byte = key[i % len(key)]
        result.append(chr(ord(c) ^ key_byte))
    return base64.b64encode(''.join(result).encode()).decode()


def _xor_decrypt(ciphertext: str) -> str:
    """简单XOR解密"""
    key = _get_encryption_key()
    try:
        data = base64.b64decode(ciphertext.encode()).decode()
        result = []
        for i, c in enumerate(data):
            key_byte = key[i % len(key)]
            result.append(chr(ord(c) ^ key_byte))
        return ''.join(result)
    except:
        return ciphertext


def is_encrypted(text: str) -> bool:
    """检查文本是否已加密"""
    if not text:
        return False
    # Base64编码的密文通常有特定长度且只含特定字符
    try:
        decoded = base64.b64decode(text.encode())
        return len(decoded) >= 32  # IV(16) + 至少16字节密文
    except:
        return False
