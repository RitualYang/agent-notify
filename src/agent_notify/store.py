from collections import deque
from datetime import datetime, timezone


class NotificationStore:
    def __init__(self, max_size: int = 100):
        self._items: deque[dict] = deque(maxlen=max_size)

    def add(self, title: str, message: str) -> dict:
        item = {
            "title": title,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._items.appendleft(item)
        return item

    def list(self, limit: int = 10) -> list[dict]:
        return list(self._items)[:limit]
