import time
from collections import OrderedDict


class AsyncLRUCache:
    def __init__(self, maxsize=128, ttl_seconds=None):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds

    async def get(self, key):
        now = time.time()
        if key in self.cache:
            value, expire_at = self.cache[key]
            if expire_at is not None and now > expire_at:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value
        return None

    async def set(self, key, value):
        expire_at = time.time() + self.ttl_seconds if self.ttl_seconds else None
        self.cache[key] = (value, expire_at)
        self.cache.move_to_end(key)
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    async def delete(self, key):
        self.cache.pop(key, None)
