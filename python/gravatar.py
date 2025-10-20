import hashlib

def get_gravatar_url(email, size=80, default='identicon', rating='g'):
    # 步骤1: 预处理 email
    email = email.lower().strip()
    
    # 步骤2: 计算 MD5 哈希
    hash_object = hashlib.md5(email.encode('utf-8'))
    hash_hex = hash_object.hexdigest()
    
    # 步骤3: 构建 URL
    url = f"https://www.gravatar.com/avatar/{hash_hex}?s={size}&d={default}&r={rating}"
    return url

# 示例使用
email = "example@example.com"
print(get_gravatar_url(email)) 
