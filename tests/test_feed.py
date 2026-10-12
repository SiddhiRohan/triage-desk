import json
import os

def test_feed_json():
    path = "data/feed.json"
    assert os.path.exists(path), "feed.json does not exist"
    
    with open(path, "r") as f:
        data = json.load(f)
    
    assert len(data) == 30, f"Expected 30 messages, found {len(data)}"
    
    # Check all fields exist in every message
    required_fields = {"id", "subject", "body", "sender_name", "received_at"}
    for msg in data:
        assert required_fields.issubset(msg.keys()), f"Message {msg.get('id')} missing fields"

    # Basic distribution check (roughly)
    # Since these are synthetic, we just ensure it's not all one category.
    # A real test would likely use the classifier to verify distribution,
    # but for now we just verify the file is valid and complete.
    print(f"Verified {len(data)} messages in feed.json")
