import json


def _payload():
    return {
        "id": "ws1", "title": "WS",
        "genre": "pop", "sub_genre": "alt-pop",
        "intent": {"topic": "t", "emotion_arc": "surrender",
                   "story": {"event": "e", "emotion": "m", "resolution": "r"}},
        "production": {"bpm": 88, "structure_template": "pop.standard", "energy_curve": [0.4]},
        "sections": [],
    }


def test_ws_sends_snapshot_on_connect(client):
    client.post("/songs", json=_payload())
    with client.websocket_connect("/ws/songs/ws1") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["song"]["title"] == "WS"


def test_ws_broadcast_on_put(client):
    client.post("/songs", json=_payload())
    with client.websocket_connect("/ws/songs/ws1") as ws:
        ws.receive_json()  # snapshot
        body = _payload()
        body["title"] = "Renamed"
        client.put("/songs/ws1", json=body)
        update = ws.receive_json()
        assert update["type"] == "update"
        assert update["song"]["title"] == "Renamed"
