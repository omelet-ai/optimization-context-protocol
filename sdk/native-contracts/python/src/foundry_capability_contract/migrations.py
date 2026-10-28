"""Schema migrations of an Optimization API's database (Capability Contract v1).

Migrations are ``NNNN_name.sql`` files applied in order, each once, under a session advisory lock so
two processes starting together do not race. Each applied file's sha256 is recorded; a recorded
file that changed, or a recorded migration whose file is gone, refuses the start
(MigrationTampered): history is not rewritten in place.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from psycopg.rows import tuple_row

__all__ = ["Migration", "MigrationTampered", "apply_migrations", "kit_migrations", "load_migrations"]

_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_LOCK_KEY = 0x0C4A_B111  # pg_advisory_lock key of the capability kit's migrations


class MigrationTampered(Exception):
    """The database's migration history does not match the files: the API must not start."""


@dataclass(frozen=True)
class Migration:
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def load_migrations(directory: Path) -> list[Migration]:
    files = sorted(path for path in directory.iterdir() if _NAME.match(path.name))
    return [Migration(path.name, path.read_text(encoding="utf-8")) for path in files]


def kit_migrations() -> list[Migration]:
    """The kit's own migrations (the job store)."""
    root = resources.files("foundry_capability_contract") / "sql"
    names = sorted(entry.name for entry in root.iterdir() if _NAME.match(entry.name))
    return [Migration(name, (root / name).read_text(encoding="utf-8")) for name in names]


def apply_migrations(conn: Any, migrations: list[Migration], *, table: str = "capability_schema_migrations") -> list[str]:
    """Apply what is new, after checking what is recorded; answers the names applied now."""
    if not re.match(r"^[a-z_][a-z0-9_]*$", table):
        raise ValueError(f"bad migrations table name {table!r}")
    applied: list[str] = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        with conn.cursor(row_factory=tuple_row) as cursor:
            recorded = dict(cursor.execute(f"SELECT name, checksum FROM {table}").fetchall())
        by_name = {migration.name: migration for migration in migrations}
        for name, checksum in recorded.items():
            migration = by_name.get(name)
            if migration is None:
                raise MigrationTampered(f"migration {name} is recorded but its file is gone")
            if migration.checksum != checksum:
                raise MigrationTampered(f"migration {name} changed after it was applied (checksum {checksum[:12]} != {migration.checksum[:12]})")
        for migration in migrations:
            if migration.name in recorded:
                continue
            conn.execute(migration.sql)
            conn.execute(f"INSERT INTO {table} (name, checksum) VALUES (%s, %s)", (migration.name, migration.checksum))
            applied.append(migration.name)
    return applied
