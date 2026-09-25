from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .errors import ValidationError

USERDATA_SCHEMA_VERSION = "1.0"


def default_userdata_directory() -> Path:
    configured = os.getenv("PLANNER_USERDATA_DIR")
    if configured:
        return Path(configured)
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            root = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            return root / "ProductionPlanner" / "userdata"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "ProductionPlanner" / "userdata"
        root = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        return root / "production-planner" / "userdata"
    return Path(__file__).resolve().parents[2] / "userdata"


class UserDataStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or default_userdata_directory()
        self.current_path: Path | None = None

    def status(self) -> dict[str, object]:
        latest = self._latest_path()
        return {
            "has_last": latest is not None,
            "last_file_name": latest.name if latest else None,
            "last_updated_at": self._read(latest)["updated_at"] if latest else None,
            "current_file_name": self.current_path.name if self.current_path else None,
        }

    def start(self, use_last: bool) -> dict[str, object]:
        latest = self._latest_path() if use_last else None
        if latest:
            self.current_path = latest
            return self._response(self._read(latest))
        payload = self._new_payload()
        self.current_path = self._new_path()
        self._write(payload)
        return self._response(payload)

    def load(self, content: bytes) -> dict[str, object]:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"invalid userdata JSON: {exc}") from exc
        payload = self._validate(payload)
        now = datetime.now(timezone.utc).isoformat()
        payload["updated_at"] = now
        payload.setdefault("created_at", now)
        self.current_path = self._new_path()
        self._write(payload)
        return self._response(payload)

    def save(self, station_counts: dict[str, int], catalog: dict[str, str | None]) -> dict[str, object]:
        if self.current_path is None:
            self.start(use_last=False)
        payload = self._read(self.current_path) if self.current_path and self.current_path.exists() else self._new_payload()
        payload["station_counts"] = self._validate_counts(station_counts)
        payload["catalog"] = catalog
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(payload)
        return self._response(payload)

    def _latest_path(self) -> Path | None:
        if not self.directory.exists():
            return None
        files = list(self.directory.glob("userdata-*.json"))
        return max(files, key=lambda path: path.stat().st_mtime_ns) if files else None

    def _new_path(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return self.directory / f"userdata-{stamp}-{uuid4().hex[:8]}.json"

    def _new_payload(self) -> dict[str, object]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "schema_version": USERDATA_SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "catalog": {},
            "station_counts": {},
        }

    def _read(self, path: Path) -> dict[str, object]:
        try:
            return self._validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"could not read userdata file {path.name}: {exc}") from exc

    def _validate(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValidationError("userdata must be a JSON object")
        version = str(payload.get("schema_version", "0"))
        if version.split(".")[0] != USERDATA_SCHEMA_VERSION.split(".")[0]:
            raise ValidationError(f"unsupported userdata schema version: {version}")
        station_counts = payload.get("station_counts", {})
        if not isinstance(station_counts, dict):
            raise ValidationError("userdata station_counts must be an object")
        payload["station_counts"] = self._validate_counts(station_counts)
        catalog = payload.get("catalog", {})
        if not isinstance(catalog, dict):
            raise ValidationError("userdata catalog must be an object")
        payload["catalog"] = catalog
        return payload

    @staticmethod
    def _validate_counts(station_counts: dict[object, object]) -> dict[str, int]:
        result: dict[str, int] = {}
        for key, value in station_counts.items():
            try:
                count = int(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"station count for {key} must be an integer") from exc
            if not isinstance(key, str) or not key or count < 1:
                raise ValidationError("userdata station counts require nonblank keys and values of at least 1")
            result[key] = count
        return result

    def _write(self, payload: dict[str, object]) -> None:
        if self.current_path is None:
            raise ValidationError("no userdata session is active")
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix="userdata-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            Path(temporary_name).replace(self.current_path)
        finally:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()

    def _response(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "file_name": self.current_path.name if self.current_path else None,
            "updated_at": payload["updated_at"],
            "catalog": payload["catalog"],
            "station_counts": payload["station_counts"],
        }
