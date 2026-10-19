import time
from threading import Lock
from typing import Any, Optional


class VectorStoreLRUCache:
    def __init__(self, maxsize: int = 20, ttl_seconds: int = 3600):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache = {} 
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, timestamp = self._cache[key]

            #Checking TTL
            if time.time() - timestamp > self.ttl_seconds:
                del self._cache[key]
                return None

            #Mark as Recently Used by popping and re-inserting
            del self._cache[key]
            self._cache[key] = (value, timestamp)
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            now = time.time()

            # If updating existing key, remove it first so re-insertion updates order
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if full
            elif len(self._cache) >= self.maxsize:
                oldest_key = next(iter(self._cache))  # Gets the first/oldest key
                del self._cache[oldest_key]

            self._cache[key] = (value, now)


    def clear_user_cache(self, user_id: int) -> int:
        # Removes all cached vectorstores belonging to a specific user_id.
        prefix = f"user_{user_id}:"
        evicted_count = 0

        with self._lock:
            # Identify all keys of this user
            keys_to_delete = [key for key in self._cache if key.startswith(prefix)]
            
            for key in keys_to_delete:
                del self._cache[key]
                evicted_count += 1

        if evicted_count > 0:
            print(f"[Cache Invalidation] Cleared {evicted_count} cached vectorstore(s) for deleted user_{user_id}")
        
        return evicted_count


vectorstore_cache = VectorStoreLRUCache(maxsize=20, ttl_seconds=3600)            