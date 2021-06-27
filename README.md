zipstream-ng
============
A modern and easy to use streamable zip file generator. It can package and stream many files and
folders on the fly without needing temporary files or excessive memory.

Includes the ability to calculate the total size of the stream before any data is actually added
(provided no compression is used). This makes it ideal for use in web applications since the total
size can be used to set the `Content-Length` header without having to generate the entire file first
(see examples below).

Other features:
 - Flexible API: Typical use cases are simple, complicated ones are possible.
 - Supports zipping data from files, as well as any iterable objects (including strings and bytes).
 - Threadsafe: won't mangle data if multiple threads are adding files or reading from the stream.
 - Includes a clone of Python's `http.server` module with zip support added. Try `python -m zipstream.server`.
 - Automatically handles Zip64 extensions: uses them if required, doesn't if not.
 - Automatically handles out of spec dates (clamps them to the range that zip files support).
 - No external dependencies.


Installation
------------
```
pip install zipstream-ng
```


Examples
--------

### zipserver (included)

A fully-functional and useful example can be found in the included
[`zipstream.server`](./zipstream/server.py) module. It's a clone of Python's built in `http.server`
with the added ability to serve multiple files and folders as a single zip file. Try it out by
installing the package and running `zipserver --help` or `python -m zipstream.server --help`


### Integration with Flask

A [Flask](https://flask.palletsprojects.com/)-based file server that serves the path at the
requested path as a zip file:

```python
import os.path
from flask import Flask, Response
from zipstream import ZipStream

app = Flask(__name__)

@app.route('/<path:path>', methods=['GET'])
def stream_zip(path):
    name = os.path.basename(os.path.normpath(path))
    zs = ZipStream.from_path(path, sized=True)
    return Response(
        zs,
        mimetype="application/zip",
        headers={
            "content-disposition": f"attachment; filename={name}.zip",
            "content-length": len(zs),
        }
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
```


### Create a local zip file (the boring use case)

```python
from zipstream import ZipStream

zs = ZipStream.from_path("/path/to/files")
with open("files.zip", "wb") as f:
    f.writelines(zs)
```


### Partial generation and last-minute file additions

It's possible to generate up the last added file without finalizing the stream. Doing this enables
adding something like a file manifest or compression log after all the files have been added.
`ZipStream` provides a `get_info` function that returns information on all the files that have been
added to the stream. In this example, all that information will be added to the zip in a file named
"manifest.json" before it's finalized.

```python
from zipstream import ZipStream
import json

def gen_zipfile()
    zs = ZipStream.from_path("/path/to/files")
    yield from zs.all_files()
    zs.add(
        json.dumps(
            zs.get_info(),
            indent=2
        ),
        "manifest.json"
    )
    yield from zs.finalize()
```


Comparison to stdlib
--------------------
Since Python 3.6 it has actually been possible to generate zip files as a stream using just the
standard library, it just hasn't been very ergonomic or efficient. Consider the typical use case of
zipping up a directory of files while streaming it over a network connection:

(note that the size of the stream is not pre-calculated in this case as this would make the stdlib
example way too long).

Using ZipStream:
```python
from zipstream import ZipStream

send_stream(
    ZipStream.from_path("/path/to/files/")
)
```

<details>
<summary>The same(ish) functionality using just the stdlib:</summary>

```python
import os
import io
from zipfile import ZipFile, ZipInfo

class Stream(io.RawIOBase):
    """An unseekable stream for the ZipFile to write to"""

    def __init__(self):
        self._buffer = bytearray()
        self._closed = False

    def close(self):
        self._closed = True

    def write(self, b):
        if self._closed:
            raise ValueError("Can't write to a closed stream")
        self._buffer += b
        return len(b)

    def readall(self):
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk

def iter_files(path):
    for dirpath, _, files in os.walk(path, followlinks=True):
        if not files:
            yield dirpath  # Preserve empty directories
        for f in files:
            yield os.path.join(dirpath, f)

def read_file(path):
    with open(path, 'rb') as fp:
        while True:
            buf = fp.read(1024 * 64)
            if not buf:
                break
            yield buf

def generate_zipstream(path):
    stream = Stream()
    with ZipFile(stream, mode='w') as zf:
        toplevel = os.path.basename(os.path.normpath(path))
        for f in iter_files(path):
            # Use the basename of the path to set the arcname
            arcname = os.path.join(toplevel, os.path.relpath(f, path))
            zinfo = ZipInfo.from_file(f, arcname)

            # Write data to the zip file then yield the stream content
            with zf.open(zinfo, mode='w') as fp:
                if zinfo.is_dir():
                    continue
                for buf in read_file(f):
                    fp.write(buf)
                    yield stream.readall()
    yield stream.readall()

send_stream(
    generate_zipstream("/path/to/files/")
)
```
</details>


Tests
-----
This package contains extensive tests. To run them, install `pytest` (`pip install pytest`) and run
`py.test` in the project directory.


License
-------
Licensed under the [GNU LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html).
