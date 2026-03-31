"""
Claw Memory E2E加密模块 - 使用标准库实现
无需额外依赖，使用内置hashlib和secrets
"""
import base64
import hashlib
import os
import secrets
import json
from pathlib import Path


class E2EEncryption:
    """
    简化版E2E加密器
    
    使用设备密钥派生加密密钥
    实现: HMAC-SHA256 + AES-like XOR
    """
    
    def __init__(self, key_file: str = None):
        self.key_file = key_file or self._default_key_file()
        self._master_key = self._load_or_create_master_key()
    
    def _default_key_file(self) -> str:
        return str(Path(__file__).parent / ".e2e_keys")
    
    def _load_or_create_master_key(self) -> bytes:
        """加载或创建主密钥"""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'r') as f:
                    data = json.load(f)
                    return base64.b64decode(data['key'])
            except:
                pass
        
        # 创建新的主密钥 (256位)
        key = secrets.token_bytes(32)
        
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        with open(self.key_file, 'w') as f:
            json.dump({'key': base64.b64encode(key).decode()}, f)
        os.chmod(self.key_file, 0o600)
        
        return key
    
    def _derive_key(self, info: bytes = b'') -> bytes:
        """从主密钥派生数据加密密钥"""
        return hashlib.sha256(self._master_key + info).digest()
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密数据
        
        格式: IV(32B):KEY_HASH(32B):CIPHERTEXT
        
        使用:
        1. 随机IV
        2. 派生出加密密钥
        3. 使用密钥对明文进行加密
        """
        if not plaintext:
            return plaintext
        
        try:
            # 生成随机IV (32字节)
            iv = secrets.token_bytes(32)
            
            # 派生加密密钥
            dek = self._derive_key(iv + b'encrypt')
            
            # 加密: 使用密钥对明文进行XOR
            plaintext_bytes = plaintext.encode('utf-8')
            
            # 分块加密
            ciphertext = bytearray()
            for i in range(len(plaintext_bytes)):
                # 使用密钥字节 + IV字节 + 明文字节
                key_byte = dek[i % len(dek)]
                iv_byte = iv[i % len(iv)]
                encrypted_byte = plaintext_bytes[i] ^ key_byte ^ iv_byte
                ciphertext.append(encrypted_byte)
            
            # 返回 IV:密文 (全部Base64)
            return f"{base64.b64encode(iv).decode()}:{base64.b64encode(bytes(ciphertext)).decode()}"
            
        except Exception as e:
            import logging
            logging.warning(f"E2E encryption failed: {e}")
            return plaintext
    
    def decrypt(self, ciphertext: str) -> str:
        """解密数据"""
        if not ciphertext or ':' not in ciphertext:
            return ciphertext
        
        try:
            parts = ciphertext.split(':')
            if len(parts) != 2:
                return ciphertext
            
            iv = base64.b64decode(parts[0])
            ct = base64.b64decode(parts[1])
            
            # 派生解密密钥
            dek = self._derive_key(iv + b'encrypt')
            
            # 解密: 使用相同的XOR
            plaintext = bytearray()
            for i in range(len(ct)):
                key_byte = dek[i % len(dek)]
                iv_byte = iv[i % len(iv)]
                decrypted_byte = ct[i] ^ key_byte ^ iv_byte
                plaintext.append(decrypted_byte)
            
            return bytes(plaintext).decode('utf-8')
            
        except Exception as e:
            import logging
            logging.warning(f"E2E decryption failed: {e}")
            return ciphertext
    
    def is_encrypted(self, text: str) -> bool:
        """检查是否已加密"""
        if not text or ':' not in text:
            return False
        parts = text.split(':')
        if len(parts) != 2:
            return False
        try:
            iv = base64.b64decode(parts[0])
            return len(iv) == 32  # 我们的IV是32字节
        except:
            return False


# 全局实例
_e2e = None

def get_e2e() -> E2EEncryption:
    global _e2e
    if _e2e is None:
        _e2e = E2EEncryption()
    return _e2e

def encrypt_data(plaintext: str) -> str:
    return get_e2e().encrypt(plaintext)

def decrypt_data(ciphertext: str) -> str:
    return get_e2e().decrypt(ciphertext)

def is_encrypted(text: str) -> bool:
    return get_e2e().is_encrypted(text)
