import json
import os
import tempfile
import unittest
from unittest.mock import patch

from connector_plugin import SimplexConnector


class TestConnectorPlugin(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_file = os.path.join(self.temp_dir.name, "connector_cache.json")
        os.environ["CONNECTOR_CACHE_FILE"] = self.cache_file
        os.environ["CONNECTOR_CACHE_TTL_SECONDS"] = "5"
        self.connector = SimplexConnector()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch.object(SimplexConnector, "_send_https", side_effect=RuntimeError("offline"))
    def test_cache_event_when_send_fails(self, _mock_send):
        event = {"type": "heartbeat", "payload": {"agent": "test"}, "timestamp": 200}
        with self.assertRaises(RuntimeError):
            with patch("connector_plugin.time.time", return_value=200):
                self.connector._send_https(event)
        with patch("connector_plugin.time.time", return_value=200):
            self.connector._cache_event(event)
            cached = self.connector._load_cache()
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0]["type"], "heartbeat")

    @patch.object(SimplexConnector, "_send_https")
    def test_sync_cache_flushes_successfully(self, mock_send):
        with patch("connector_plugin.time.time", return_value=200):
            with open(self.cache_file, "w", encoding="utf-8") as file:
                json.dump([{"type": "heartbeat", "payload": {}, "timestamp": 199}], file)
            self.connector._sync_cache()
        self.assertEqual(mock_send.call_count, 1)
        with open(self.cache_file, "r", encoding="utf-8") as file:
            remaining = json.load(file)
        self.assertEqual(remaining, [])

    def test_expired_cache_is_removed(self):
        with patch("connector_plugin.time.time", return_value=200):
            with open(self.cache_file, "w", encoding="utf-8") as file:
                json.dump([
                    {"type": "old", "payload": {}, "timestamp": 100},
                    {"type": "new", "payload": {}, "timestamp": 199}
                ], file)
            cached = self.connector._load_cache()
            self.assertEqual(len(cached), 1)
            self.assertEqual(cached[0]["type"], "new")


if __name__ == "__main__":
    unittest.main()
