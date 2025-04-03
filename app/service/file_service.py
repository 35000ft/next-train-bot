import time

from botpy.types import message

uploaded_file_cache = {}
max_cache_files = 128
ttl = 3600


async def cache_uploaded_file(key: str, media: message.Media):
    now = time.time()

    # If media is not permanent, calculate expiration timestamp; permanent media get an infinite lifetime.
    if media['ttl'] != 0:
        media['expires_at'] = now + media['ttl']
    else:
        media['expires_at'] = float('inf')  # 永久有效

    # If key already exists, update its media information
    if key in uploaded_file_cache:
        uploaded_file_cache[key] = media
        return

    # If cache is not full, add the new media directly.
    if len(uploaded_file_cache) < max_cache_files:
        uploaded_file_cache[key] = media
        return

    # Remove expired entries first.
    expired_keys = [k for k, m in uploaded_file_cache.items() if m['expires_at'] <= now]
    for k in expired_keys:
        del uploaded_file_cache[k]

    # If after cleaning expired entries the cache has room, add the media.
    if len(uploaded_file_cache) < max_cache_files:
        uploaded_file_cache[key] = media
        return

    # Cache is still full: find and evict the entry that will expire the soonest.
    evict_key = min(uploaded_file_cache, key=lambda k: uploaded_file_cache[k]['expires_at'])
    del uploaded_file_cache[evict_key]

    # Finally, add the new media.
    uploaded_file_cache[key] = media


async def get_cached_uploaded_file(key: str) -> message.Media | None:
    if not key:
        return None
    return uploaded_file_cache.get(key, None)
