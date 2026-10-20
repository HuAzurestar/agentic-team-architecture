"""Real HTTP/storage tests; no desktop notifications are sent by this suite."""

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import bridge
import notify


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "messages.db"
        self.server = notify._Server(("127.0.0.1", 0), self.database)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.environment = patch.dict("os.environ", {"AOPC_NOTIFY_URL": self.url})
        self.environment.start()
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()
        self.environment.stop()
        self.temporary.cleanup()

    def http(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def test_function_delivers_unicode_multiline_in_order(self):
        messages = ["你好，AOPC\n第二行 👋", "下一条消息"]
        for message in messages:
            self.assertIsNone(notify.notify(message))
        events = notify.request_json("/api/events?after=0&wait=0")["messages"]
        self.assertEqual([item["message"] for item in events], messages)

    def test_concurrent_senders_do_not_lose_messages(self):
        messages = [f"message {index}" for index in range(16)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(notify.notify, messages))
        received = self.server.store.events(0, 0)
        self.assertCountEqual([item["message"] for item in received], messages)
        self.assertEqual([item["id"] for item in received], list(range(1, 17)))

    def test_function_rejects_invalid_message_without_network(self):
        with patch.object(notify, "request_json") as request:
            for message in (None, 12, "", " \n\t", "中" * 10923):
                with self.subTest(message_type=type(message).__name__):
                    with self.assertRaises((TypeError, ValueError)):
                        notify.notify(message)
            request.assert_not_called()

    def test_http_rejects_malformed_messages_and_wrong_origin(self):
        for body in (b"{", b"[]", b"null", b"{}", b'{"message": 1}',
                     b'{"message": " "}', json.dumps({"message": "x" * 32769}).encode()):
            self.assertEqual(self.http("POST", "/notify", body, {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.http("POST", "/notify", b"{}", {"Content-Type": "text/plain"})[0], 400)
        headers = {"Content-Type": "application/json", "Origin": "https://other.example"}
        self.assertEqual(self.http("POST", "/notify", b'{"message":"x"}', headers)[0], 400)
        self.assertEqual(self.server.store.latest_id(), 0)

    def test_details_escape_html_and_keep_full_text(self):
        message = '<script>alert("hello")</script>\n中文 & ' + "long " * 200
        notify.notify(message)
        status, page = self.http("GET", "/messages/1")
        self.assertEqual(status, 200)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("中文 &amp; " + "long " * 200, page)
        self.assertIn('href="/messages/1"', self.http("GET", "/")[1])
        for path in ("/messages/999", "/messages/bad", "/messages/-1", "/messages/" + "9" * 60):
            self.assertEqual(self.http("GET", path)[0], 404)

    def test_storage_and_cursor_identity_survive_reopen(self):
        notify.notify("persisted")
        reopened = notify.Store(self.database)
        self.assertEqual(reopened.instance, self.server.store.instance)
        self.assertEqual(reopened.get(1)["message"], "persisted")
        self.assertEqual(reopened.add("next")["id"], 2)

    def test_long_poll_wakes_on_message_and_times_out_without_one(self):
        started = threading.Event()

        def receive():
            started.set()
            return notify.request_json("/api/events?after=0&wait=2")

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(receive)
            started.wait(1)
            time.sleep(0.05)
            notify.notify("wake up")
            self.assertEqual(future.result(timeout=2)["messages"][0]["message"], "wake up")
        self.assertEqual(notify.request_json("/api/events?after=1&wait=0")["messages"], [])

    def test_events_page_in_order_without_dropping_older_messages(self):
        for index in range(103):
            self.server.store.add(str(index))
        first = notify.request_json("/api/events?after=0&wait=0")["messages"]
        second = notify.request_json(f'/api/events?after={first[-1]["id"]}&wait=0')["messages"]
        self.assertEqual([item["id"] for item in first + second], list(range(1, 104)))
        self.assertEqual(len(notify.request_json("/api/messages")["messages"]), 100)

    def test_invalid_event_parameters_are_rejected(self):
        for query in ("after=-1", "after=no", "wait=26", "wait=-1", "after=" + "9" * 60):
            self.assertEqual(self.http("GET", "/api/events?" + query)[0], 400)

    def test_bridge_cursor_resumes_and_new_install_skips_old_history(self):
        path = Path(self.temporary.name) / "cursor.json"
        health = {"instance": "first", "last_id": 12}
        self.assertEqual(bridge.load_state(path, health), 12)
        bridge.save_state(path, "first", 4)
        self.assertEqual(bridge.load_state(path, health), 4)
        self.assertEqual(bridge.load_state(path, {"instance": "new", "last_id": 2}), 2)
        path.write_text("corrupt", encoding="utf-8")
        self.assertEqual(bridge.load_state(path, health), 12)

    def test_native_toast_links_body_and_button_to_exact_message(self):
        try:
            import windows_toasts
        except ImportError:
            self.skipTest("Install requirements-windows.txt for native toast XML validation")
        toast = bridge.build_toast({"id": 123, "message": "hello" * 100}, self.url)
        self.assertEqual(toast.launch_action, self.url + "/messages/123")
        self.assertEqual(toast.actions[0].launch, toast.launch_action)
        self.assertLessEqual(len(toast.text_fields[1]), 240)
        self.assertEqual(toast.tag, "123")
        # Build the actual library XML without displaying a notification.
        toaster = windows_toasts.InteractableWindowsToaster("XML test")
        xml = toaster._setup_toast(toast, False).xmlDocument.get_xml()
        self.assertIn('activationType="protocol"', xml)
        self.assertIn(toast.launch_action, xml)


if __name__ == "__main__":
    unittest.main()
