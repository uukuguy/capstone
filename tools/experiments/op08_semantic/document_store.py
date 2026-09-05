"""Disk metadata for the isolated document parser and iterative emitter."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import BinaryIO

from tools.experiments.op08_semantic.object_index import DiskObjectIndex


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    parent: int | None
    kind: str
    object_id: int | None
    offset: int
    length: int
    invalid: bool
    state: str
    key_offset: int
    key_length: int
    next_position: int
    emit_started: bool
    emit_position: int
    emit_count: int


class DocumentStore:
    """The owner supplies a fresh autocommit DB and an append-only blob file.

    Node parent links plus persisted states are the parse/output stack; there
    is no Python collection growing with tree depth or member cardinality.
    A failed whole-document operation discards this entire scratch instance.
    """

    def __init__(self, connection: sqlite3.Connection, blobs: BinaryIO) -> None:
        self.connection = connection
        self.index = DiskObjectIndex(connection, blobs)
        connection.execute(
            "CREATE TABLE nodes(id INTEGER PRIMARY KEY,parent INTEGER,kind TEXT NOT NULL,"
            "object_id INTEGER,offset INTEGER NOT NULL,length INTEGER NOT NULL,"
            "invalid INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'first',"
            "key_offset INTEGER NOT NULL DEFAULT 0,key_length INTEGER NOT NULL DEFAULT 0,"
            "next_position INTEGER NOT NULL DEFAULT 0,emit_started INTEGER NOT NULL DEFAULT 0,"
            "emit_position INTEGER NOT NULL DEFAULT -1,emit_count INTEGER NOT NULL DEFAULT 0)"
        ).close()
        connection.execute(
            "CREATE TABLE array_edges(parent INTEGER,position INTEGER,child INTEGER NOT NULL,"
            "PRIMARY KEY(parent,position)) WITHOUT ROWID"
        ).close()

    def create(self, kind: str, parent: int | None, offset: int = 0,
               length: int = 0, invalid: bool = False) -> int:
        object_id = self.index.new_object() if kind == "object" else None
        with closing(self.connection.execute(
            "INSERT INTO nodes(parent,kind,object_id,offset,length,invalid) VALUES(?,?,?,?,?,?)",
            (parent, kind, object_id, offset, length, invalid),
        )) as cursor:
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def node(self, node_id: int) -> Node:
        with closing(self.connection.execute("SELECT * FROM nodes WHERE id=?", (node_id,))) as cursor:
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("document node missing")
        return Node(*row)

    def state(self, node_id: int, state: str) -> None:
        self.connection.execute("UPDATE nodes SET state=? WHERE id=?", (state, node_id)).close()

    def key(self, node_id: int, offset: int, length: int) -> None:
        self.connection.execute(
            "UPDATE nodes SET key_offset=?,key_length=?,state='colon' WHERE id=?",
            (offset, length, node_id),
        ).close()

    def attach(self, child: int) -> int | None:
        parent_id = self.node(child).parent
        if parent_id is None:
            return None
        parent = self.node(parent_id)
        if parent.kind == "object":
            assert parent.object_id is not None
            self.index.put(parent.object_id, parent.key_offset, parent.key_length, child)
        else:
            self.connection.execute(
                "INSERT INTO array_edges VALUES(?,?,?)", (parent_id, parent.next_position, child)
            ).close()
        self.connection.execute(
            "UPDATE nodes SET state='comma',next_position=next_position+1 WHERE id=?", (parent_id,)
        ).close()
        return parent_id

    def start_output(self, node_id: int) -> None:
        self.connection.execute("UPDATE nodes SET emit_started=1 WHERE id=?", (node_id,)).close()

    def advance_output(self, node_id: int, position: int, emitted: bool) -> None:
        self.connection.execute(
            "UPDATE nodes SET emit_position=?,emit_count=emit_count+? WHERE id=?",
            (position, int(emitted), node_id),
        ).close()

    def array_after(self, node_id: int, position: int) -> tuple[int, int] | None:
        with closing(self.connection.execute(
            "SELECT position,child FROM array_edges WHERE parent=? AND position>? ORDER BY position LIMIT 1",
            (node_id, position),
        )) as cursor:
            return cursor.fetchone()
