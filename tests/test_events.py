from src.events.bus import EventBus


def test_publish_returns_event_id(tmp_db):
    bus = EventBus(tmp_db)
    event_id = bus.publish("PostCreated", {"post_id": "abc"})
    assert isinstance(event_id, str) and len(event_id) > 0


def test_consume_returns_published_events(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "abc"})
    events = bus.consume("PostCreated")
    assert len(events) == 1
    assert events[0].type == "PostCreated"
    assert events[0].payload == {"post_id": "abc"}


def test_consume_marks_events_processed(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "abc"})
    bus.consume("PostCreated")
    events_again = bus.consume("PostCreated")
    assert len(events_again) == 0


def test_consume_filters_by_type(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "a"})
    bus.publish("LikeAdded", {"post_id": "a", "from": "x"})
    events = bus.consume("LikeAdded")
    assert len(events) == 1
    assert events[0].type == "LikeAdded"
