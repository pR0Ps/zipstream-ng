#!/usr/bin/env python

import http.client
from http.server import HTTPServer
import io
import os
import threading
import time
import urllib.parse
import zipfile

import pytest

from zipstream.server import ZippingHTTPRequestHandler


@pytest.mark.parametrize("timezone", [None, "EST5"])
def test_post_last_modified(tmp_path, monkeypatch, timezone):
    if timezone is not None and not hasattr(time, "tzset"):
        pytest.skip("Changing the local timezone requires time.tzset")

    # Exercise both the default timezone and a non-UTC timezone: file mtimes
    # become naive local datetimes in ZipStream, but HTTP dates must use GMT.
    with monkeypatch.context() as patch:
        if timezone is not None:
            patch.setenv("TZ", timezone)
            time.tzset()
        try:
            patch.chdir(str(tmp_path))
            path = tmp_path / "example.txt"
            path.write_bytes(b"example")
            timestamp = 1700000000
            os.utime(str(path), (timestamp, timestamp))

            server = HTTPServer(("127.0.0.1", 0), ZippingHTTPRequestHandler)
            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()
            client = http.client.HTTPConnection(*server.server_address, timeout=5)
            try:
                client.request(
                    "POST", "/", urllib.parse.urlencode({"files": "example.txt"}),
                    {"Content-Type": "application/x-www-form-urlencoded"},
                )
                response = client.getresponse()
                body = response.read()
                assert response.status == 200
                assert response.getheader("Content-Type") == "application/zip"
                assert int(response.getheader("Content-Length")) == len(body)
                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                    assert archive.read("example.txt") == b"example"
                assert response.getheader("Last-Modified") == "Tue, 14 Nov 2023 22:13:20 GMT"
            finally:
                client.close()
                server.shutdown()
                server.server_close()
                thread.join()
        finally:
            # Undo TZ before refreshing the process timezone, even on failure.
            patch.undo()
            if timezone is not None:
                time.tzset()
