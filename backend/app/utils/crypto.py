from Crypto.Cipher import AES
import base64
import os

# 这里需要和 Go 代码使用相同的密钥
CRYPTO_KEY = os.getenv("PHONE_CRYPTO_KEY", "").encode("utf-8")

def decrypt_phone(encrypted_text: str) -> str:
    try:
        # base64 解码
        decoded = base64.b64decode(encrypted_text)

        # 获取 IV (前16字节)
        iv = decoded[:AES.block_size]

        # 创建解密器
        cipher = AES.new(CRYPTO_KEY, AES.MODE_CBC, iv)

        # 解密剩余部分
        decrypted = cipher.decrypt(decoded[AES.block_size:])

        # 去除填充
        padding = 0
        for i in range(len(decrypted)-1, -1, -1):
            if decrypted[i] != 0:
                break
            padding += 1

        return decrypted[:-padding].decode('utf-8')
    except Exception as e:
        print(f"解密失败: {str(e)}")
        return ""

def encrypt_phone(phone: str) -> str:
    try:
        # 将手机号转换为字节
        phone_bytes = phone.encode('utf-8')

        # 生成随机IV
        iv = b'\x00' * AES.block_size  # 使用全零IV以保持一致性

        # 创建加密器
        cipher = AES.new(CRYPTO_KEY, AES.MODE_CBC, iv)

        # 计算需要的填充
        padding_length = AES.block_size - (len(phone_bytes) % AES.block_size)
        if padding_length == 0:
            padding_length = AES.block_size

        # 添加填充
        padded_data = phone_bytes + (b'\x00' * padding_length)

        # 加密数据
        encrypted = cipher.encrypt(padded_data)

        # 组合IV和加密数据，然后进行base64编码
        result = base64.b64encode(iv + encrypted).decode('utf-8')

        return result
    except Exception as e:
        print(f"加密失败: {str(e)}")
        return ""
