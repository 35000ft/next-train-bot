import random
import string
import time
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
