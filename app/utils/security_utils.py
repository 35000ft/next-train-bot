import base64
import hashlib
import random
import string
import time
from datetime import datetime
from typing import Dict


class CodeManager:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, tuple[str, float]] = {}

    def generate_code(self, value: str) -> str:
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        expire_at = time.time() + self.ttl_seconds
        self._store[code] = (value, expire_at)
        return code

    def validate_code(self, code: str) -> str | None:
        item = self._store.get(code)
        if not item:
            return None
        value, expire_at = item
        if time.time() > expire_at:
            del self._store[code]
            return None
        return value


def generate_invite_code(secret_key: str, date: str = None, length: int = 8) -> str:
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    raw = f"{date}-{secret_key}"

    # 使用SHA256生成哈希
    hash_bytes = hashlib.sha256(raw.encode()).digest()

    # 使用 base32 编码（更适合邀请码，不区分大小写）
    b32_code = base64.b32encode(hash_bytes).decode('utf-8').replace('=', '')

    return b32_code[:length].upper()
