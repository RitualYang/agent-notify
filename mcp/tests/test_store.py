from agent_notify.store import NotificationStore


def test_store_add_and_list():
    store = NotificationStore(max_size=5)
    store.add("Title 1", "Message 1")
    store.add("Title 2", "Message 2")
    items = store.list(limit=10)
    assert len(items) == 2
    assert items[0]["title"] == "Title 2"  # most recent first
    assert items[1]["title"] == "Title 1"


def test_store_max_size():
    store = NotificationStore(max_size=3)
    for i in range(5):
        store.add(f"Title {i}", f"Message {i}")
    items = store.list(limit=10)
    assert len(items) == 3


def test_store_list_limit():
    store = NotificationStore(max_size=100)
    for i in range(10):
        store.add(f"Title {i}", f"Message {i}")
    items = store.list(limit=3)
    assert len(items) == 3


def test_store_item_has_timestamp():
    store = NotificationStore()
    store.add("T", "M")
    items = store.list()
    assert "timestamp" in items[0]
    assert "title" in items[0]
    assert "message" in items[0]
