from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import ValidationError

SCHEMA_VERSION = "1.0"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE items (
  item_key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('raw','producible')),
  unit TEXT NOT NULL DEFAULT 'unit',
  average_value TEXT,
  value_basis TEXT,
  notes TEXT
);
CREATE TABLE stations (
  station_key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  notes TEXT
);
CREATE TABLE recipes (
  recipe_key TEXT PRIMARY KEY,
  output_item_key TEXT NOT NULL REFERENCES items(item_key),
  process_name TEXT NOT NULL,
  output_quantity TEXT NOT NULL,
  station_key TEXT NOT NULL REFERENCES stations(station_key),
  duration_seconds INTEGER NOT NULL CHECK(duration_seconds >= 0),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  notes TEXT
);
CREATE UNIQUE INDEX one_active_recipe_per_item
ON recipes(output_item_key) WHERE is_active = 1;
CREATE TABLE ingredients (
  recipe_key TEXT NOT NULL REFERENCES recipes(recipe_key) ON DELETE CASCADE,
  item_key TEXT NOT NULL REFERENCES items(item_key),
  quantity TEXT NOT NULL,
  PRIMARY KEY(recipe_key, item_key)
);
CREATE TABLE capacity_profiles (
  profile_key TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE capacities (
  profile_key TEXT NOT NULL REFERENCES capacity_profiles(profile_key) ON DELETE CASCADE,
  station_key TEXT NOT NULL REFERENCES stations(station_key),
  station_count INTEGER NOT NULL CHECK(station_count >= 1),
  PRIMARY KEY(profile_key, station_key)
);
CREATE TABLE sources (
  source_key TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT,
  accessed_date TEXT,
  notes TEXT
);
"""


def create_database(path: Path, rows: dict[str, list[dict[str, object]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA_SQL)
        with connection:
            connection.executemany("INSERT INTO metadata(key,value) VALUES(:key,:value)", rows["metadata"])
            connection.execute("INSERT INTO metadata(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,))
            connection.executemany(
                "INSERT INTO items(item_key,name,kind,unit,average_value,value_basis,notes) VALUES(:item_key,:name,:kind,:unit,:average_value,:value_basis,:notes)",
                rows["items"],
            )
            connection.executemany(
                "INSERT INTO stations(station_key,name,notes) VALUES(:station_key,:name,:notes)", rows["stations"]
            )
            connection.executemany(
                "INSERT INTO recipes(recipe_key,output_item_key,process_name,output_quantity,station_key,duration_seconds,is_active,notes) VALUES(:recipe_key,:output_item_key,:process_name,:output_quantity,:station_key,:duration_seconds,:is_active,:notes)",
                rows["recipes"],
            )
            connection.executemany(
                "INSERT INTO ingredients(recipe_key,item_key,quantity) VALUES(:recipe_key,:item_key,:quantity)",
                rows["ingredients"],
            )
            connection.executemany(
                "INSERT INTO capacity_profiles(profile_key,name) VALUES(:profile_key,:name)", rows["capacity_profiles"]
            )
            connection.executemany(
                "INSERT INTO capacities(profile_key,station_key,station_count) VALUES(:profile_key,:station_key,:station_count)",
                rows["capacities"],
            )
            connection.executemany(
                "INSERT INTO sources(source_key,title,url,accessed_date,notes) VALUES(:source_key,:title,:url,:accessed_date,:notes)",
                rows["sources"],
            )
    finally:
        connection.close()


def validate_database(path: Path) -> None:
    if not path.is_file():
        raise ValidationError(f"database does not exist: {path}")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if not row or row[0].split(".")[0] != SCHEMA_VERSION.split(".")[0]:
                raise ValidationError("unsupported or missing database schema version")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValidationError(f"database integrity check failed: {integrity}")
    except sqlite3.Error as exc:
        raise ValidationError(f"invalid planner database: {exc}") from exc


@contextmanager
def open_database(path: Path) -> Iterator[sqlite3.Connection]:
    validate_database(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def database_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

