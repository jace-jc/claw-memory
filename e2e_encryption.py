"""
Claw Memory E2E加密模块 v2.0 - 安全重构版
使用 cryptography 库实现 AES-256-GCM 认证加密
"""
import os
import base64
import secrets
from pathlib import Path
from typing import Optional, Dict, Any

# 尝试导入 cryptography，如未安装则禁用加密
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class E2EEncryption:
    """
    生产级E2E加密器
    
    加密方案：
    - 算法：AES-256-GCM（认证加密）
    - 密钥派生：PBKDF2-HMAC-SHA256，100万次迭代
    - IV：每次加密随机生成96位
    - 盐值：随机32字节
    """
    
    def __init__(self, key_file: str = None, password: str = None):
        """
        Args:
            key_file: 密钥文件路径（如不提供则使用password）
            password: 主密码（用于派生加密密钥）
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError(
                "cryptography库未安装。运行：pip install cryptography"
            )
        
        self.key_file = key_file
        self.password = password
        self._master_key = self._load_or_create_key()
    
    def _load_or_create_key(self) -> bytes:
        """加载或创建主密钥"""
        if self.key_file and os.path.exists(self.key_file):
            # 从文件加载加密后的密钥
            return self._load_from_file()
        
        # 生成新密钥
        if not self.password:
            raise ValueError("必须提供password或key_file")
        
        # 派生密钥
        salt = secrets.token_bytes(32)
        key = self._derive_key(self.password, salt)
        
        # 保存到文件（如果指定了路径）
        if self.key_file:
            self._save_to_file(key, salt)
        
        return key
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """使用PBKDF2派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256位
            salt=salt,
            iterations=1_000_000,  # 100万次迭代
        )
        return kdf.derive(password.encode('utf-8'))
    
    def _load_from_file(self) -> bytes:
        """从文件加载密钥"""
        with open(self.key_file, 'rb') as f:
            data = f.read()
        
        # 解密存储的密钥
        salt = data[:32]
        encrypted_key = data[32:]
        
        if not self.password:
            raise ValueError("需要密码才能解密密钥文件")
        
        # 使用密码派生密钥解密
        kdf_key = self._derive_key(self.password, salt)
        aesgcm = AESGCM(kdf_key)
        
        # 解密（格式：nonce(12) + ciphertext + tag(16)）
        nonce = encrypted_key[:12]
        ciphertext = encrypted_key[12:]
        
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def _save_to_file(self, key: bytes, salt: bytes):
        """安全保存密钥到文件"""
        if not self.password:
            return
        
        # 使用密码派生密钥加密主密钥
        kdf_key = self._derive_key(self.password, salt)
        aesgcm = AESGCM(kdf_key)
        
        nonce = secrets.token_bytes(12)
        encrypted_key = aesgcm.encrypt(nonce, key, None)
        
        # 格式：salt(32) + nonce(12) + ciphertext
        data = salt + nonce + encrypted_key
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        
        # 写入文件（权限600）
        with open(self.key_file, 'wb') as f:
            f.write(data)
        os.chmod(self.key_file, 0o600)
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密数据
        
        Returns:
            base64编码的密文（格式：salt(32) + nonce(12) + ciphertext）
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography库未安装")
        
        # 生成随机盐值和IV
        salt = secrets.token_bytes(32)
        nonce = secrets.token_bytes(12)
        
        # 派生数据加密密钥
        dek = self._derive_key_from_master(salt)
        
        # 加密
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # 组合：salt + nonce + ciphertext
        encrypted_data = salt + nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('ascii')
    
    def decrypt(self, ciphertext: str) -> str:
        """解密数据"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography库未安装")
        
        # 解码
        data = base64.b64decode(ciphertext.encode('ascii'))
        
        # 解析：salt(32) + nonce(12) + ciphertext
        salt = data[:32]
        nonce = data[32:44]
        encrypted = data[44:]
        
        # 派生密钥
        dek = self._derive_key_from_master(salt)
        
        # 解密
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, encrypted, None)
        
        return plaintext.decode('utf-8')
    
    def _derive_key_from_master(self, salt: bytes) -> bytes:
        """从主密钥派生数据加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(self._master_key)
    
    @staticmethod
    def is_available() -> bool:
        """检查加密功能是否可用"""
        return CRYPTO_AVAILABLE


# 便捷函数
def encrypt_data(data: str, password: str) -> str:
    """使用密码加密数据"""
    enc = E2EEncryption(password=password)
    return enc.encrypt(data)


def decrypt_data(ciphertext: str, password: str) -> str:
    """使用密码解密数据"""
    enc = E2EEncryption(password=password)
    return enc.decrypt(ciphertext)


def is_encrypted(text: str) -> bool:
    """检查文本是否已加密"""
    if not text:
        return False
    try:
        # 尝试base64解码
        decoded = base64.b64decode(text)
        # 检查长度（salt 32 + nonce 12 + 最小密文）
        return len(decoded) >= 44 + 16
    except:
        return False
