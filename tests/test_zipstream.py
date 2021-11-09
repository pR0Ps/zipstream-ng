#!/usr/bin/env python

import hashlib
import io
import itertools
import json
import logging
import os
import random
import sys
import time
import zipfile
import zlib

import pytest

import zipstream
from zipstream import ZipStream


PY36 = sys.version_info < (3, 7)
PY35 = sys.version_info < (3, 6)

FILES = [
    ("empty", 0),
    ("byte", 1),
    ("kbyte", 1024),
    ("mbyte", 1024 * 1024),
]


# Patch is_dir onto ZipInfo objects in 3.5 to make testing easier
@pytest.fixture(autouse=PY35)
def add_is_dir(monkeypatch):
    monkeypatch.setattr(
        zipfile.ZipInfo, "is_dir",
        zipstream.ZipStreamInfo.is_dir,
        raising=False
    )


@pytest.fixture(scope="session")
def files(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    paths = []
    for f in FILES:
        path = d / f[0]
        data = _randbytes(f[1])
        hash_ = hashlib.md5(data).hexdigest()
        crc32 = zlib.crc32(data) & 0xFFFFFFFF

        path.write_bytes(data)
        paths.append((path, hash_, crc32))

    return paths


################################
# Test helpers
################################

def _randbytes(n):
    # Backported from Python 3.9
    if not n:
        return b''
    return random.getrandbits(n * 8).to_bytes(n, 'little')

def _get_zip(data):
    if not isinstance(data, io.IOBase):
        if not isinstance(data, (bytes, bytearray)):
            data = b''.join(data)
        data = io.BytesIO(data)

    return zipfile.ZipFile(data)


def _verify_zip_contains(zfile, pathdata):
    path, hash_, crc32 = pathdata
    path = os.path.basename(str(path))
    zinfo = zfile.getinfo(path)
    assert zinfo.filename == path
    assert zinfo.CRC == crc32
    assert hashlib.md5(zfile.read(zinfo)).hexdigest() == hash_


def _assert_equal_zips(z1, z2):
    assert z1.comment == z2.comment
    z1i = sorted(z1.infolist(), key=lambda x: x.filename)
    z2i = sorted(z2.infolist(), key=lambda x: x.filename)
    print(z1i)
    print(z2i)
    assert len(z1i) == len(z2i)
    for x1, x2, in zip(z1i, z2i):
        assert x1.filename == x2.filename
        assert x1.file_size == x2.file_size
        assert x1.compress_size == x2.compress_size
        assert x1.date_time == x2.date_time
        assert x1.CRC == x2.CRC
        assert x1.compress_type == x2.compress_type

def _gen_rand():
    for x in range(10):
        yield _randbytes(1024)


################################
# Tests start
################################

@pytest.mark.parametrize("ct", [
    zipfile.ZIP_STORED,
    zipfile.ZIP_LZMA,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2
])
def test_zipstream_compression(files, ct):
    """Test that all types of compression properly compress and extract"""
    zs = ZipStream(compress_type=ct)
    for f in files:
        zs.add_path(f[0])

    zf = _get_zip(zs)
    zinfos = zf.infolist()
    assert len(zinfos) == len(files)

    for zinfo in zinfos:
        assert zinfo.compress_type == ct

    for f in files:
        _verify_zip_contains(zf, f)


@pytest.mark.parametrize("zip64", [False, True])
def test_zipstream_normal_paths(monkeypatch, files, zip64):
    """Test adding paths and iterating"""
    if zip64:
        monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 100)
        monkeypatch.setattr(zipstream, "ZIP64_LIMIT", 100)

    zs = ZipStream()
    for f in files:
        zs.add_path(f[0])

    zf = _get_zip(zs)
    assert len(zf.infolist()) == len(files)

    for f in files:
        _verify_zip_contains(zf, f)


def test_zipstream_all_then_footer_paths(files):
    """Test adding paths and iterating over all files, then footer"""
    zs = ZipStream()
    for f in files:
        zs.add_path(f[0])

    data = io.BytesIO()
    data.writelines(zs.all_files())
    data.writelines(zs.footer())

    zf = _get_zip(data)
    assert len(zf.infolist()) == len(files)

    for f in files:
        _verify_zip_contains(zf, f)


def test_per_file_iteration(files):
    """Test iterating per-file while adding files works"""
    zs = ZipStream()
    data = b''
    assert zs.num_streamed() == 0
    assert zs.num_queued() == 0
    assert zs.is_empty()
    assert not zs
    zs.add("a", "a")
    zs.add("b", "b")
    zs.add("c", "c")
    assert zs.num_streamed() == 0
    assert zs.num_queued() == 3
    assert not zs.is_empty()
    assert zs
    data += b''.join(zs.file())
    assert zs.num_streamed() == 1
    assert zs.num_queued() == 2
    assert not zs.is_empty()
    assert zs
    data += b''.join(zs.all_files())
    assert zs.num_streamed() == 3
    assert zs.num_queued() == 0
    assert not zs.is_empty()
    assert zs
    zs.add("d", "d")
    assert zs.num_streamed() == 3
    assert zs.num_queued() == 1
    assert not zs.is_empty()
    assert zs
    data += b''.join(zs.finalize())
    assert zs.num_streamed() == 4
    assert zs.num_queued() == 0
    assert not zs.is_empty()
    assert zs
    assert len(_get_zip(data).infolist()) == 4


def test_footer_empty(files):
    """Test calling footer before iterating files results in a valid but empty zip"""
    zs = ZipStream()
    for f in files:
        zs.add_path(f[0])

    data = io.BytesIO()
    data.writelines(zs.footer())

    # Minimum size of a zip file is 22 bytes
    # (just the end of central directory record)
    assert len(data.getvalue()) == 22
    zf = _get_zip(data)
    assert len(zf.infolist()) == 0


def test_footer_partial(files):
    """Test calling footer before iterating all files results in valid but partial zip"""
    zs = ZipStream()
    for f in files:
        zs.add_path(f[0])

    data = io.BytesIO()
    data.writelines(zs.file())
    data.writelines(zs.footer())

    zf = _get_zip(data)
    assert len(zf.infolist()) == 1

    _verify_zip_contains(zf, files[0])


@pytest.mark.parametrize("ct", [
    zipfile.ZIP_STORED,
    zipfile.ZIP_LZMA
])
def test_compress_level_python_36(monkeypatch, ct):
    """Test that using compress_level on <3.7 produces an error"""

    # Test that the module-level attribute is set correctly
    assert zipstream.PY36_COMPAT == PY36

    # Patch it to let the test work on all versions
    monkeypatch.setattr(zipstream, "PY36_COMPAT", True)

    with pytest.raises(ValueError, match="compress_level is not supported"):
        ZipStream(compress_type=ct, compress_level=1)

    zs = ZipStream(compress_type=ct)
    with pytest.raises(ValueError, match="compress_level is not supported"):
        zs.add_path(".", compress_level=1)
    with pytest.raises(ValueError, match="compress_level is not supported"):
        zs.add("data", "data.bin", compress_level=1)

    # Test that basic compression still works
    zs.add(b"moredata", "data.bin")
    zf = _get_zip(zs)
    zinfos = zf.infolist()
    assert len(zinfos) == 1
    assert zinfos[0].filename == "data.bin"
    assert zf.read(zinfos[0]) == b"moredata"


@pytest.mark.skipif(PY36, reason="Tests compress_level (Python 3.7+ only)")
@pytest.mark.parametrize("ct", [
    zipfile.ZIP_STORED,
    zipfile.ZIP_LZMA
])
def test_non_effective_compression_warn(caplog, ct):
    """Test warning for non-effective compression level settings"""
    caplog.set_level(logging.WARNING)

    ZipStream(compress_type=ct)
    assert "no effect" not in caplog.text

    ZipStream(compress_type=ct, compress_level=1)
    assert "no effect" in caplog.text


@pytest.mark.skipif(PY36, reason="Tests compress_level (Python 3.7+ only)")
@pytest.mark.parametrize("ct", [
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2
])
def test_invalid_compression(ct):
    """Test values outside of valid ones cause an error"""
    ZipStream(compress_type=ct)

    invalid = [-1, 10]
    if ct == zipfile.ZIP_BZIP2:
        invalid.append(0)

    for x in invalid:
        with pytest.raises(ValueError):
            ZipStream(compress_type=ct, compress_level=x)
        with pytest.raises(ValueError):
            ZipStream().add_path(".", compress_type=ct, compress_level=x)
        with pytest.raises(ValueError):
            ZipStream().add(".", arcname=".", compress_type=ct, compress_level=x)

        zs = ZipStream(compress_type=ct)
        with pytest.raises(ValueError):
            zs.add(".", arcname=".", compress_level=x)

        zs = ZipStream(compress_level=x)
        with pytest.raises(ValueError):
            zs.add(".", arcname=".", compress_type=ct)


def test_creating_dirs_with_data():
    """Test creating directories works except when adding data to them"""
    zs = ZipStream()
    zs.add(None, "folder0/")
    zs.add(b'', "folder1/")
    zs.add("", "folder2/")
    with pytest.raises(ValueError):
        zs.add("data", "folder3/")

    zinfos = _get_zip(zs).infolist()
    assert len(zinfos) == 3
    for i in range(3):
        assert zinfos[i].filename == "folder{}/".format(i)
        assert zinfos[i].is_dir()
        assert zinfos[i].file_size == 0
        assert zinfos[i].compress_size == 0


def test_empty_folders_preserved_recursive(tmpdir):
    """Test that recursively adding a directory preserves empty files and folders in it"""
    t = tmpdir.mkdir("top")
    t.mkdir("empty")
    t.join("file.txt").write(b'')

    zinfos = sorted(_get_zip(ZipStream.from_path(t)).infolist(), key=lambda x: x.filename)

    assert len(zinfos) == 2
    assert zinfos[0].filename == "top/empty/"
    assert zinfos[0].is_dir()
    assert zinfos[0].file_size == 0
    assert zinfos[0].compress_size == 0

    assert zinfos[1].filename == "top/file.txt"
    assert not zinfos[1].is_dir()
    assert zinfos[1].file_size == 0
    assert zinfos[1].compress_size == 0

def test_recursion_disable(tmpdir):
    """Test that recursion can be disabled to just add a single (empty) folder"""
    t = tmpdir.mkdir("top")
    t.mkdir("empty")
    t.join("file.txt").write(b'')

    zinfos = _get_zip(ZipStream.from_path(t, recurse=False)).infolist()

    assert len(zinfos) == 1
    assert zinfos[0].filename == "top/"
    assert zinfos[0].is_dir()
    assert zinfos[0].file_size == 0
    assert zinfos[0].compress_size == 0


@pytest.mark.parametrize("data", [
    "this is a string",
    b'these are some bytes',
    bytearray(b'this is a bytearray'),
    [b'a', b'list', b'of', b'bytes'],
    _gen_rand()
])
def test_adding_data(data):
    """Test adding non-files"""
    zs = ZipStream()

    tostore = data
    if isinstance(data, str):
        # Strings will be utf-8 encoded
        data = data.encode("utf-8")
    elif not isinstance(data, (bytes, str, bytearray)):
        # tee the iterator and get the contents from it so they can be checked
        # against what's put into the stream
        tostore, data = itertools.tee(data)
        data = b''.join(data)

    # Test arcname is required
    with pytest.raises(ValueError):
        zs.add(tostore, "")

    zs.add(tostore, "data.bin")
    zf = _get_zip(zs)

    zinfos = zf.infolist()
    assert len(zinfos) == 1

    from_file = zf.read(zinfos[0])
    assert from_file == data


@pytest.mark.parametrize("data", [0, 1, object(), type(None)])
def test_adding_invalid_data(data):
    zs = ZipStream()
    with pytest.raises(TypeError):
        zs.add(data, "test")


@pytest.mark.parametrize("data", [
    ["strs", "cannot", "be", "added"],
    range(10),
    ZipStream,
])
def test_adding_undetectable_invalid_data(data):
    """Test iterables that yield bad data are only detected at generation time"""
    zs = ZipStream()
    zs.add(data, "test")
    with pytest.raises(TypeError):
        list(zs)


def test_directory_links_without_infinite_recursion(tmpdir):
    """Ensure adding paths follows directory links without being vulnerable to
    infinite recursion"""

    t = tmpdir.mkdir("top")
    if not hasattr(t, "mksymlinkto"):
        pytest.skip("mksymlinkto not supported - can't test infinite recursion")

    o = tmpdir.mkdir("other")
    o.join("validfile").write("this is valid")
    b = t.mkdir("mid").mkdir("bottom")
    # Create cycle
    b.join("evil").mksymlinkto("../../../")
    # Create valid dirlink
    b.join("notevil").mksymlinkto("../../../other")

    pathnames = (
        "top/",
        "top/mid/",
        "top/mid/bottom/",
        "top/mid/bottom/evil/",
        "top/mid/bottom/notevil/validfile"
    )

    zinfos = sorted(_get_zip(ZipStream.from_path(t)).infolist(), key=lambda x: x.filename)
    assert len(zinfos) == len(pathnames)
    for x, n in zip(zinfos, pathnames):
        assert x.filename == n
        if "/validfile" in n:
            assert not x.is_dir()
            assert x.file_size != 0
            assert x.compress_size != 0
        else:
            assert x.is_dir()
            assert x.file_size == 0
            assert x.compress_size == 0

def test_adding_missing_path(tmpdir):
    with pytest.raises(ValueError):
        ZipStream.from_path(tmpdir.join("doesntexist"))


def test_adding_comment(caplog):
    caplog.set_level(logging.WARNING)

    zs = ZipStream()
    zs.comment = "test"
    assert zs.comment == "test".encode("utf-8")

    zs.comment = None
    assert not zs.comment

    with pytest.raises(TypeError):
        zs.comment += "test"
    zs.comment += "test".encode("utf-8")

    zs.comment = None
    assert not zs.comment

    zs.comment = bytearray(b"test")
    assert zs.comment == "test".encode("utf-8")

    c = b'this is a test with a big comment' + bytes(zipfile.ZIP_MAX_COMMENT)
    l = len(c)
    assert "too long" not in caplog.text
    zs.comment = c
    assert "too long" in caplog.text
    assert len(zs.comment) != l
    assert len(zs.comment) == zipfile.ZIP_MAX_COMMENT

    with pytest.raises(TypeError):
        zs.comment = 10


def test_finalizing():
    # Finalize by iteration
    zs = ZipStream()
    _get_zip(zs)
    assert zs._final

    # Finalize explicitly
    zs = ZipStream()
    _get_zip(zs.finalize())
    assert zs._final

    # Finalize using footer
    zs = ZipStream()
    _get_zip(zs.footer())
    assert zs._final

    # Doesn't finalize if just asking for file data
    data = b''
    zs = ZipStream()
    zs.add("", "a")
    data += b''.join(zs.file())
    assert not zs._final
    data += b''.join(zs.file())
    assert not zs._final
    zs.add("", "b")
    data += b''.join(zs.all_files())
    assert not zs._final
    data += b''.join(zs.footer())
    assert zs._final
    _get_zip(data)


def test_adding_after_complete():
    """Test that adding files/changing the comment after the stream has been
    finalized is an error"""
    zs = ZipStream()
    list(zs)
    assert zs._final
    with pytest.raises(RuntimeError):
        zs.add("", "b")
    with pytest.raises(RuntimeError):
        zs.add_path(".")
    with pytest.raises(RuntimeError):
        zs.comment = "comment"


def test_asking_for_files_after_complete():
    """Test that trying to iterate files after the stream has been finalized
    returns nothing"""
    zs = ZipStream()
    list(zs)
    assert zs._final
    assert not list(zs)
    assert not list(zs.file())
    assert not list(zs.all_files())
    assert not list(zs.footer())
    assert not list(zs.finalize())


@pytest.mark.parametrize("date", [
    (0, 0, 0, 0, 0, 0),
    (1979, 12, 31, 23, 59, 59),
    (1980, 0, 0 ,0, 0, 0),  # breaks zipfile.ZipFile
    (2107, 99, 0, 0, 0, 0),  # breaks zipfile.ZipFile
    (2108, 0, 0, 0, 0, 0),
    (9999, 99, 99 ,99, 99, 99),
])
def test_invalid_dates(monkeypatch, date):
    """Test that dates outside the range that the zip format supports are
    automatically clamped to the closest valid value"""

    def fakelocaltime():
        return date
    monkeypatch.setattr(time, "localtime", fakelocaltime)

    zs = ZipStream()
    zs.add("a", "a.txt")
    zinfos = _get_zip(zs).infolist()

    assert len(zinfos) == 1

    if date < (2000, 1, 1, 0, 0, 0):
        assert zinfos[0].date_time == (1980, 1, 1, 0, 0, 0)
    else:
        # The seconds are 58 instead of 59 because times encoded in zip files
        # only have 2 second precision (rounded down)
        assert zinfos[0].date_time == (2107, 12, 31, 23, 59, 58)


def test_get_info(monkeypatch):

    faketime = (1980, 1, 1, 0, 0, 0)

    def fakelocaltime():
        return faketime
    monkeypatch.setattr(time, "localtime", fakelocaltime)

    data = bytearray()
    zs = ZipStream(compress_type=zipfile.ZIP_STORED)
    zs.add(None, "empty/", compress_type=zipfile.ZIP_DEFLATED)
    zs.add(b"test", "text.txt", compress_type=zipfile.ZIP_BZIP2, compress_level=5 if not PY36 else None)
    zs.add(b"test", "text2.txt")
    assert zs.num_queued() == 3
    assert len(zs.get_info()) == 0
    data += b''.join(zs.all_files())
    assert zs.num_queued() == 0
    info = zs.get_info()
    assert len(info) == 3

    assert info[0] == {
        "name": "empty/",
        "size": 0,
        "compressed_size": 0,
        "datetime": "1980-01-01T00:00:00",
        "CRC": 0,
        "compress_type": zipfile.ZIP_DEFLATED,
        "compress_level": None,
        "extract_version": zipfile.DEFAULT_VERSION
    }
    assert info[1] == {
        "name": "text.txt",
        "size": 4,
        "compressed_size": 40,
        "datetime": "1980-01-01T00:00:00",
        "CRC": 3632233996,
        "compress_type": zipfile.ZIP_BZIP2,
        "compress_level": 5 if not PY36 else None,
        "extract_version": zipfile.BZIP2_VERSION
    }
    assert info[2] == {
        "name": "text2.txt",
        "size": 4,
        "compressed_size": 4,
        "datetime": "1980-01-01T00:00:00",
        "CRC": 3632233996,
        "compress_type": zipfile.ZIP_STORED,
        "compress_level": None,
        "extract_version": zipfile.DEFAULT_VERSION
    }

    zs.add(json.dumps(info, indent=2), "manifest.json")
    assert zs.num_queued() == 1
    data += bytes(zs)
    assert zs.num_queued() == 0
    assert len(zs.get_info()) == 4

    zinfos = _get_zip(data).infolist()
    assert len(zinfos) == 4


@pytest.mark.skipif(PY35, reason="Requires zipfiles to support unseekable streams (Python 3.6+ only)")
def test_readme_stdlib_comparison(tmpdir):
    """Make sure the comparison is accurate"""

    # Set up the stdlib version scaffolding
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

    # Create directory structure
    t = tmpdir.mkdir("top")
    t.mkdir("empty")
    t.join("empty.txt").write('')
    t.join("test.txt").write('test')
    f = t.mkdir("filled")
    f.join("file.bin").write_binary(b'\x00\x01\xFF')

    # Can't make symlinks on some platforms
    if hasattr(t, "mksymlinkto"):
        f.join("file2.bin").mksymlinkto('file.bin')

        o = tmpdir.mkdir("othertop")
        o.join("other.txt").write('other')
        f.join("notevil").mksymlinkto('../../othertop')

        # TODO: make stdlib version handle infinte loops
        #f.join("evil").mksymlinkto('../')

    _assert_equal_zips(
        _get_zip(generate_zipstream(t)),
        _get_zip(ZipStream.from_path(t))
    )

def test_add_duplicate_file():
    """Test adding multiple files with the same name works"""
    zs = ZipStream(sized=True)
    zs.add(b"test", "test.txt")
    zs.add(b"another test", "test.txt")

    calculated = len(zs)
    data = bytes(zs)
    assert len(data) == calculated

    zf = _get_zip(data)

    zinfos = zf.infolist()
    assert len(zinfos) == 2

    assert zf.read(zinfos[0]) == b"test"
    assert zf.read(zinfos[1]) == b"another test"


def test_unsized_zipstream_len_typeerror():
    """Test that an unsized ZipStream raises a TypeError when aske for the length"""
    zs = ZipStream(sized=False)
    assert not zs.sized

    with pytest.raises(TypeError):
        len(ZipStream(sized=False))


@pytest.mark.parametrize("zip64", [False, True])
def test_sized_zipstream(monkeypatch, files, zip64):
    """Test a sized ZipStream accurately calculates its final size"""

    if zip64:
        monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 100)
        monkeypatch.setattr(zipstream, "ZIP64_LIMIT", 100)

    with pytest.raises(ValueError):
        ZipStream(sized=True, compress_type=zipfile.ZIP_DEFLATED)
    with pytest.raises(ValueError):
        ZipStream(sized=True, compress_type=zipfile.ZIP_LZMA)
    with pytest.raises(ValueError):
        ZipStream(sized=True, compress_type=zipfile.ZIP_BZIP2)

    with pytest.raises(ValueError):
        ZipStream.from_path(".", sized=True, compress_type=zipfile.ZIP_DEFLATED)

    szs = ZipStream(sized=True)
    for f in files:
        szs.add_path(f[0])

    # Specifying null/useless compression works
    szs.add(None, "a_dir/", compress_type=zipfile.ZIP_STORED)
    szs.add(_gen_rand(), "random.txt", compress_type=None)
    szs.add(b"data", "data.bin", compress_level=None)
    szs.add("text", "data.text", compress_level=10 if not PY36 else None)

    # Specifying any actual compression raises errors
    with pytest.raises(ValueError):
        szs.add("invalid", "invalid", compress_type=zipfile.ZIP_DEFLATED)
    with pytest.raises(ValueError):
        szs.add("invalid", "invalid", compress_type=zipfile.ZIP_LZMA)
    with pytest.raises(ValueError):
        szs.add("invalid", "invalid", compress_type=zipfile.ZIP_BZIP2)

    assert szs.sized
    calculated = len(szs)

    data = bytes(szs)
    assert calculated == len(data)

    zf = _get_zip(data)
    for f in files:
        _verify_zip_contains(zf, f)

    assert len(zf.infolist()) == len(files) + 4


@pytest.mark.parametrize("zip64", [False, True])
def test_sized_zipstream_size_while_adding(monkeypatch, files, zip64):
    """Test a sized ZipStream accurately calculates its final size while adding
    files"""

    if zip64:
        monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 100)
        monkeypatch.setattr(zipstream, "ZIP64_LIMIT", 100)

    # Get sizes of zips with a subset of files in them
    sizes = []
    for l in range(len(files) + 1):
        szs = ZipStream(sized=True)
        for i in range(l):
            szs.add_path(files[i][0])

        s = len(szs)
        assert s == sum(len(x) for x in szs)
        sizes.append(s)

    if zip64:
        # files > 100b use zip64 extensions, requiring more space
        assert sizes == [22, 124, 301, 1483, 1050217]
    else:
        assert sizes == [22, 124, 225, 1351, 1050029]

    # Add files and check the sizes match the above values
    szs = ZipStream(sized=True)
    assert sizes[0] == len(szs)
    for i, f in enumerate(files, 1):
        szs.add_path(f[0])
        assert sizes[i] == len(szs)

    # make sure adding comment adds to the size
    szs.comment = "this is a comment"
    assert sizes[-1] + len(szs.comment) == len(szs)

    # check against size of actual generated bytes
    calculated = len(szs)
    data = bytes(szs)
    assert calculated == len(data)

    # check contents
    zf = _get_zip(data)
    assert len(zf.infolist()) == len(files)
    for f in files:
        _verify_zip_contains(zf, f)


# Warning: skippped because it creates a 4GB+ temp file
@pytest.mark.skip
def test_zip64_real(tmpdir):
    """Test compressing a large file using Zip64 extensions works"""
    large_file = tmpdir.join("large.bin")
    zip_file = tmpdir.join("out.zip")

    # Generate a big empty file that requires Zip64 extensions to handle
    # bookended by 1MB of random data. Also generate a small file with random
    # data to test the header offset of it being over non-zip64 limits.
    datasize = 1024 * 1024
    startdata = _randbytes(datasize)
    enddata = _randbytes(datasize)
    smalldata = _randbytes(datasize)

    # Write large file
    with open(str(large_file), 'wb') as fp:
        fp.write(startdata)
        fp.seek(zipfile.ZIP64_LIMIT, io.SEEK_CUR)
        fp.write(enddata)

    # Write as a stream to a zip file
    zs = ZipStream()
    zs.add_path(large_file)
    zs.add(smalldata, "small.bin")
    with open(str(zip_file), 'wb') as fp:
        fp.writelines(zs)

    with zipfile.ZipFile(str(zip_file), 'r') as zf:
        zinfos = zf.infolist()
        assert len(zinfos) == 2

        # Read the data and make sure it's the same as what was put in
        with zf.open("large.bin", 'r') as fp:
            assert startdata == fp.read(datasize)
            if PY36:
                # No support for seeking <3.7 - read it all in 128MB chunks
                per = 1024 * 1024 * 128
                rem = zipfile.ZIP64_LIMIT % per
                for _ in range(zipfile.ZIP64_LIMIT // per):
                    fp.read(per)
                fp.read(rem)
            else:
                fp.seek(zipfile.ZIP64_LIMIT, io.SEEK_CUR)
            assert enddata == fp.read()

        with zf.open("small.bin", 'r') as fp:
            assert smalldata == fp.read()
