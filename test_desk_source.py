"""对本地来源登记的传输和取页合同做回归验证。"""

import json
from pathlib import Path
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from desk_source import open_desk


class DeskSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = Path(__file__).with_name("records")
        cls.server = open_desk(cls.records, 0)
        cls.thread = Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.01})
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def read(self, suffix):
        with urlopen(self.origin + suffix, timeout=2) as response:
            self.assertEqual(response.headers.get_content_charset(), "utf-8")
            return json.load(response)

    def test_list_sources(self):
        names = {item["name"] for item in self.read("/sources")["sources"]}
        self.assertEqual(names, {path.stem for path in self.records.glob("*.json")})

    def test_every_record_is_available_in_order(self):
        for entry in self.read("/sources")["sources"]:
            with self.subTest(source=entry["name"]):
                page_path = f"/sources/{entry['name']}?limit=2&offset="
                offset = 0
                records = []
                while offset is not None:
                    page = self.read(page_path + str(offset))
                    self.assertEqual(page["feed"], entry["name"])
                    records.extend(page["records"])
                    offset = page["next_offset"]
                self.assertEqual(len(records), entry["count"])
                with (self.records / f"{entry['name']}.json").open(encoding="utf-8") as source:
                    self.assertEqual(records, json.load(source))

    def test_invalid_queries_are_distinguishable(self):
        with self.assertRaises(HTTPError) as missing:
            self.read("/sources/absent")
        self.assertEqual(missing.exception.code, 404)
        with self.assertRaises(HTTPError) as invalid:
            self.read(f"/sources/{next(iter(self.server.desk.feeds))}?offset=-1")
        self.assertEqual(invalid.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
