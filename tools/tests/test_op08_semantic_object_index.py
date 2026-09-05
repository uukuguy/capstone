from __future__ import annotations

import importlib.util
import io
import os
import sqlite3
import sys
import tempfile
import tracemalloc
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "experiments/op08_semantic/object_index.py"
_SPEC = importlib.util.spec_from_file_location("op08_index", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
DiskObjectIndex = _MODULE.DiskObjectIndex
ObjectIndexError = _MODULE.ObjectIndexError


@pytest.fixture
def storage(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "index.sqlite3")
    with tempfile.TemporaryFile() as keys:
        try:
            yield connection, keys
        finally:
            connection.close()


def append_key(keys, payload: bytes) -> tuple[int, int]:
    keys.seek(0, os.SEEK_END)
    start = keys.tell()
    keys.write(payload)
    return start, len(payload)


def test_first_position_last_value_and_object_isolation(storage) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    first, second = index.new_object(), index.new_object()
    a, b, another_a = [append_key(keys, key) for key in [b'"a"', b'"b"', b'"a"']]
    index.put(first, *a, 1)
    index.put(first, *b, 2)
    replacement = index.put(first, *another_a, 3)
    index.put(second, *another_a, 4)
    members = list(index.members(first))
    assert [(m.position, m.value_id) for m in members] == [(0, 3), (1, 2)]
    assert (replacement.key_offset, replacement.key_length) == a
    assert [m.value_id for m in index.members(second)] == [4]
    assert keys.tell() == sum(length for _, length in [a, b, another_a])
    assert not keys.closed
    assert not connection.in_transaction


def test_digest_collision_requires_exact_key_bytes(storage, monkeypatch) -> None:
    monkeypatch.setattr(_MODULE, "_digest_range", lambda *_: b"x" * 32)
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    for value_id, payload in enumerate([b'"aa"', b'"bb"', b'"aa"'], 1):
        index.put(object_id, *append_key(keys, payload), value_id)
    assert [m.value_id for m in index.members(object_id)] == [3, 2]


def test_member_after_is_keyset_read_without_retained_iterator(storage) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    a, b = append_key(keys, b'"a"'), append_key(keys, b'"b"')
    assert index.member_after(object_id, -1) is None
    index.put(object_id, *a, 1)
    index.put(object_id, *b, 2)
    assert index.member_after(object_id, -1).value_id == 1
    index.put(object_id, *a, 3)
    assert index.member_after(object_id, 0).value_id == 2
    assert index.member_after(object_id, 1) is None
    with pytest.raises(ObjectIndexError):
        index.member_after(999, -1)
    with pytest.raises(ValueError):
        index.member_after(object_id, True)


@pytest.mark.parametrize("offset,length", [(-1, 1), (False, 1), (0, 0), (0, -1), (0, True)])
def test_invalid_range_arguments(storage, offset: int, length: int) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    with pytest.raises(ValueError):
        index.put(object_id, offset, length, 1)


def test_missing_object_and_past_eof_range_reject(storage) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    key = append_key(keys, b'"a"')
    with pytest.raises(ObjectIndexError):
        index.put(123, *key, 1)
    with pytest.raises(ObjectIndexError):
        list(index.members(123))
    object_id = index.new_object()
    with pytest.raises(ObjectIndexError):
        index.put(object_id, 0, 100, 1)
    assert list(index.members(object_id)) == []


def test_rejects_memory_database_and_memory_keys(storage) -> None:
    connection, keys = storage
    memory = sqlite3.connect(":memory:")
    try:
        with pytest.raises(ObjectIndexError):
            DiskObjectIndex(memory, keys)
        with pytest.raises(ObjectIndexError):
            DiskObjectIndex(connection, io.BytesIO())
    finally:
        memory.close()


def test_existing_schema_and_external_transaction_preserved(storage) -> None:
    connection, keys = storage
    connection.execute("CREATE TABLE user_data(value)")
    with pytest.raises(ObjectIndexError):
        DiskObjectIndex(connection, keys)
    assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchone() == ("user_data",)
    connection.execute("DROP TABLE user_data")
    index = DiskObjectIndex(connection, keys)
    connection.execute("BEGIN")
    with pytest.raises(ObjectIndexError):
        index.new_object()
    assert connection.in_transaction
    connection.rollback()


def test_lazy_iteration_prevents_writes_until_closed(storage) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    key = append_key(keys, b'"a"')
    index.put(object_id, *key, 1)
    iterator = index.members(object_id)
    assert next(iterator).value_id == 1
    with pytest.raises(ObjectIndexError):
        index.put(object_id, *key, 2)
    iterator.close()
    index.put(object_id, *key, 2)
    assert next(index.members(object_id)).value_id == 2


@pytest.mark.parametrize("fault", [sqlite3.OperationalError("private failure"), KeyboardInterrupt(), SystemExit()])
def test_transaction_failure_rolls_back_insert_and_position(tmp_path: Path, fault: BaseException) -> None:
    class FaultConnection(sqlite3.Connection):
        armed = False

        def execute(self, sql, parameters=()):
            cursor = super().execute(sql, parameters)
            if self.armed and sql.startswith("UPDATE objects SET next_position"):
                self.armed = False
                cursor.close()
                raise fault
            return cursor

    connection = sqlite3.connect(tmp_path / "fault.sqlite3", factory=FaultConnection)
    with tempfile.TemporaryFile() as keys:
        try:
            index = DiskObjectIndex(connection, keys)
            object_id = index.new_object()
            key = append_key(keys, b'"a"')
            connection.armed = True
            expected = type(fault) if not isinstance(fault, Exception) else ObjectIndexError
            with pytest.raises(expected) as error:
                index.put(object_id, *key, 1)
            if isinstance(fault, Exception):
                assert error.value.__cause__ is fault
                assert "private failure" not in str(error.value)
            assert not connection.in_transaction
            assert list(index.members(object_id)) == []
            assert index.put(object_id, *key, 2).position == 0
        finally:
            connection.close()


def test_attached_database_and_nondefault_rows_are_rejected(storage) -> None:
    connection, keys = storage
    connection.execute("ATTACH DATABASE ':memory:' AS other")
    with pytest.raises(ObjectIndexError):
        DiskObjectIndex(connection, keys)
    connection.execute("DETACH DATABASE other")
    connection.row_factory = sqlite3.Row
    with pytest.raises(ObjectIndexError):
        DiskObjectIndex(connection, keys)
    connection.row_factory = None
    assert connection.execute("SELECT name FROM sqlite_schema").fetchone() is None


def test_schema_initialization_is_atomic(tmp_path: Path) -> None:
    class Failing(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("CREATE INDEX"):
                raise sqlite3.OperationalError("injected schema failure")
            return super().execute(sql, parameters)

    connection = sqlite3.connect(tmp_path / "schema.sqlite3", factory=Failing)
    with tempfile.TemporaryFile() as keys:
        try:
            with pytest.raises(ObjectIndexError):
                DiskObjectIndex(connection, keys)
            assert connection.execute("SELECT name FROM sqlite_schema").fetchone() is None
            assert not connection.in_transaction and not keys.closed
        finally:
            connection.close()


def test_rollback_failure_poison_does_not_mask_primary(tmp_path: Path) -> None:
    original = sqlite3.OperationalError("primary payload")

    class Failing(sqlite3.Connection):
        armed = False

        def execute(self, sql, parameters=()):
            if self.armed and sql.startswith("ROLLBACK TO"):
                raise sqlite3.OperationalError("cleanup payload")
            cursor = super().execute(sql, parameters)
            if self.armed and sql.startswith("UPDATE objects SET next_position"):
                cursor.close()
                raise original
            return cursor

    connection = sqlite3.connect(tmp_path / "rollback.sqlite3", factory=Failing)
    with tempfile.TemporaryFile() as keys:
        try:
            index = DiskObjectIndex(connection, keys)
            object_id = index.new_object()
            key = append_key(keys, b'"a"')
            connection.armed = True
            with pytest.raises(ObjectIndexError) as error:
                index.put(object_id, *key, 1)
            assert error.value.__cause__ is original
            assert any("cleanup failed" in note for note in original.__notes__)
            with pytest.raises(ObjectIndexError, match="unusable"):
                index.new_object()
            connection.armed = False
            connection.rollback()
            assert not keys.closed
        finally:
            connection.close()


@pytest.mark.parametrize("mode", ["short", "empty", "nonbytes", "overread", "exception"])
def test_key_read_protocol(storage, monkeypatch, mode: str) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    key = append_key(keys, b'"abcdefgh"')
    original = os.pread
    fault = OSError("private key payload")

    def changed(fd: int, size: int, offset: int):
        if mode == "short":
            return original(fd, min(2, size), offset)
        if mode == "empty":
            return b""
        if mode == "nonbytes":
            return None
        if mode == "overread":
            return b"x" * (size + 1)
        raise fault

    monkeypatch.setattr(os, "pread", changed)
    if mode == "short":
        index.put(object_id, *key, 1)
        index.put(object_id, *key, 2)
        assert [m.value_id for m in index.members(object_id)] == [2]
    else:
        with pytest.raises(ObjectIndexError) as error:
            index.put(object_id, *key, 1)
        if mode == "exception":
            assert error.value.__cause__ is fault
        assert list(index.members(object_id)) == []


def test_string_primitive_normalizes_equivalent_keys(storage) -> None:
    spec = importlib.util.spec_from_file_location("index_string_input", _PATH.with_name("strings.py"))
    assert spec is not None and spec.loader is not None
    strings = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = strings
    spec.loader.exec_module(strings)
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    for value_id, raw in enumerate([b'"a"', b'"\\u0061"'], 1):
        offset = keys.tell()
        info = strings.read_json_string(strings.UTF8Cursor(io.BytesIO(raw)), keys)
        index.put(object_id, offset, info.byte_count, value_id)
    assert [m.value_id for m in index.members(object_id)] == [2]


@pytest.mark.parametrize("count", [256, 4096])
def test_member_cardinality_keeps_python_iteration_lazy(storage, count: int) -> None:
    connection, keys = storage
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    for value_id in range(1, count + 1):
        index.put(object_id, *append_key(keys, f'"key{value_id}"'.encode()), value_id)
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    try:
        total = 0
        for member in index.members(object_id):
            total += member.value_id
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert total == count * (count + 1) // 2
    assert peak - before < 128 * 1024
    assert connection.execute("PRAGMA cache_size").fetchone() == (-1024,)
    assert connection.execute("PRAGMA mmap_size").fetchone() == (0,)
    assert connection.execute("PRAGMA temp_store").fetchone() == (1,)
    print({"members": count, "iteration_peak_bytes": peak - before})


@pytest.mark.parametrize("size", [8 * 1024 * 1024, 64 * 1024 * 1024])
def test_huge_duplicate_keys_remain_bounded(storage, monkeypatch, size: int) -> None:
    connection, keys = storage
    block = b"a" * 65536
    for _ in range(2):
        keys.write(b'"')
        for _ in range(size // len(block)):
            keys.write(block)
        keys.write(b'"')
    keys.flush()
    index = DiskObjectIndex(connection, keys)
    object_id = index.new_object()
    original = os.pread
    max_request = 0

    def counted(fd: int, requested: int, offset: int) -> bytes:
        nonlocal max_request
        max_request = max(max_request, requested)
        assert 0 < requested <= 65536
        return original(fd, requested, offset)

    monkeypatch.setattr(os, "pread", counted)
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    try:
        index.put(object_id, 0, size + 2, 1)
        replaced = index.put(object_id, size + 2, size + 2, 2)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert replaced.position == 0 and replaced.key_offset == 0
    assert [m.value_id for m in index.members(object_id)] == [2]
    assert peak - before <= 4 * 1024 * 1024
    assert max_request == 65536
    print({"key_body_bytes": size, "peak_bytes": peak - before, "max_pread": max_request})
