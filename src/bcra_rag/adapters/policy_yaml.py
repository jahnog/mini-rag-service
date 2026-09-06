from __future__ import annotations

from pathlib import Path
from typing import Any

from bcra_rag.domain.guardrails.types import Policy, RailConfig

_DEFAULT = Path(__file__).resolve().parents[1] / "guardrails" / "policy.yaml"
_STAGES = frozenset({"input", "retrieve", "generate", "output"})


def default_policy_path() -> Path:
    return _DEFAULT


def load_policy(path: Path | None = None) -> Policy:
    target = path or _DEFAULT
    payload = _parse_simple(target.read_text(encoding="utf-8"))
    rails: list[RailConfig] = []
    for item in payload.get("rails") or []:
        if not isinstance(item, dict):
            continue
        stage = str(item["stage"])
        if stage not in _STAGES:
            raise ValueError(f"unknown rail stage: {stage}")
        rails.append(
            RailConfig(
                id=str(item["id"]),
                stage=stage,  # type: ignore[arg-type]
                enabled=bool(item.get("enabled", True)),
                enforce=bool(item.get("enforce", True)),
                params=dict(item.get("params") or {}),
            )
        )
    return Policy(
        version=int(payload.get("version") or 2),
        enforce=bool(payload.get("enforce", True)),
        rails=rails,
    )


def _parse_simple(text: str) -> dict[str, Any]:
    """Minimal YAML subset for the packaged policy (no PyYAML required)."""
    version = 2
    enforce = True
    rails: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("version:"):
            version = int(line.split(":", 1)[1].strip())
            continue
        if line.startswith("enforce:"):
            enforce = line.split(":", 1)[1].strip().lower() == "true"
            continue
        if line.startswith("- {") and line.endswith("}"):
            rails.append(_inline_map(line[line.index("{") + 1 : -1]))
    return {"version": version, "enforce": enforce, "rails": rails}


def _inline_map(body: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    params: dict[str, Any] = {}
    in_params = False
    for part in body.split(","):
        piece = part.strip()
        if piece.startswith("params:"):
            in_params = True
            rest = piece.split(":", 1)[1].strip()
            if rest.startswith("{"):
                rest = rest[1:]
            if rest.endswith("}"):
                rest = rest[:-1]
                in_params = False
            if rest:
                key, value = rest.split(":", 1)
                params[key.strip()] = _scalar(value.strip())
            continue
        if in_params:
            if piece.endswith("}"):
                piece = piece[:-1]
                in_params = False
            if ":" in piece:
                key, value = piece.split(":", 1)
                params[key.strip()] = _scalar(value.strip())
            continue
        key, value = piece.split(":", 1)
        out[key.strip()] = _scalar(value.strip())
    if params:
        out["params"] = params
    return out


def _scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value
