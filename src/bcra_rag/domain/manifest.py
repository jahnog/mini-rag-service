from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bcra_rag.domain.urls import TO_DOC_ID, comm_number, normalize_comm_id


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class Manifest:
    path: Path
    last_refresh: str | None = None
    to_as_of: str | None = None
    last_comm_id: str | None = None
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.is_file():
            return cls(path=path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return cls(path=path)
        documents = raw.get("documents") or {}
        if not isinstance(documents, dict):
            documents = {}
        return cls(
            path=path,
            last_refresh=raw.get("last_refresh"),
            to_as_of=raw.get("to_as_of"),
            last_comm_id=raw.get("last_comm_id"),
            documents=documents,
        )

    @property
    def has_checkpoint(self) -> bool:
        return bool(self.documents)

    @property
    def is_complete(self) -> bool:
        return bool(self.last_refresh) and self.has_checkpoint

    def sha256_for(self, doc_id: str) -> str | None:
        entry = self.documents.get(doc_id)
        if not entry:
            return None
        value = entry.get("sha256")
        return str(value) if value else None

    def is_indexed(self, doc_id: str) -> bool:
        entry = self.documents.get(doc_id)
        if not entry:
            return False
        if "indexed" not in entry:
            return True
        return bool(entry["indexed"])

    def checkpoint(self, doc_id: str, entry: dict[str, Any]) -> None:
        previous = self.documents.get(doc_id) or {}
        self.documents[doc_id] = {**previous, **entry}
        self._refresh_last_comm()
        self.save()

    def mark_complete(self) -> None:
        self.last_refresh = utc_now()
        self._refresh_last_comm()
        self.save()

    def _refresh_last_comm(self) -> None:
        numbers: list[int] = []
        for key in self.documents:
            if key == TO_DOC_ID:
                continue
            try:
                numbers.append(comm_number(normalize_comm_id(key)))
            except ValueError:
                continue
        if numbers:
            self.last_comm_id = f"A{max(numbers)}"

    def save(self) -> None:
        if not self.documents and not self.last_refresh:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_refresh": self.last_refresh,
            "to_as_of": self.to_as_of,
            "last_comm_id": self.last_comm_id,
            "documents": self.documents,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
