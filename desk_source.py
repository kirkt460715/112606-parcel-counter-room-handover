"""本地联调所用的独立业务记录读取端。"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class ObservationDesk:
    def __init__(self, directory):
        self.feeds = {}
        for path in sorted(directory.glob("*.json")):
            with path.open(encoding="utf-8") as stream:
                rows = json.load(stream)
            if not isinstance(rows, list):
                raise ValueError(f"{path.name} 需要一组记录")
            keys = [row.get("id") for row in rows]
            if any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys):
                raise ValueError(f"{path.name} 的来源记录编号无效")
            self.feeds[path.stem] = rows
        if not self.feeds:
            raise ValueError("没有可供读取的来源登记")

    def page(self, feed, offset, limit):
        rows = self.feeds[feed]
        end = min(offset + limit, len(rows))
        return dict(feed=feed, records=rows[offset:end], next_offset=end if end < len(rows) else None)


class DeskHandler(BaseHTTPRequestHandler):
    def reply(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        desk = self.server.desk
        if url.path == "/sources":
            self.reply(200, {"sources": [{"name": key, "count": len(rows)} for key, rows in desk.feeds.items()]})
            return
        parts = url.path.split("/")
        if len(parts) != 3 or parts[1] != "sources" or parts[2] not in desk.feeds:
            self.reply(404, {"error": "无此来源"})
            return
        parameters = parse_qs(url.query, keep_blank_values=True)
        try:
            offset = int(parameters.get("offset", ["0"])[0])
            limit = int(parameters.get("limit", ["20"])[0])
            if offset < 0 or not 1 <= limit <= 50 or any(len(values) != 1 for values in parameters.values()):
                raise ValueError
        except ValueError:
            self.reply(400, {"error": "分页范围无效"})
            return
        self.reply(200, desk.page(parts[2], offset, limit))

    def log_message(self, format, *args):
        pass


def open_desk(directory, port):
    desk = ObservationDesk(directory)
    server = ThreadingHTTPServer(("127.0.0.1", port), DeskHandler)
    server.desk = desk
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--records", type=Path, default=Path(__file__).with_name("records"))
    options = parser.parse_args()
    with open_desk(options.records, options.port) as server:
        print(f"资料端已启动，端口 {server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
