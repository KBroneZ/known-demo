"""Finding record and verdict logic shared by every rule."""

from __future__ import annotations

from dataclasses import asdict, dataclass

BLOCK, WARN, INFO = "block", "warn", "info"
SEVERITY_RANK = {INFO: 0, WARN: 1, BLOCK: 2}

VERDICT_BLOCK = "BLOQUEAR"
VERDICT_FIX = "CORREGIR"
VERDICT_OK = "PUBLICAR"
VERDICT_RANK = {VERDICT_OK: 0, VERDICT_FIX: 1, VERDICT_BLOCK: 2}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    line: int  # 1-based line in the post file; 0 = whole file
    evidence: str
    message: str
    layer: str = "deterministic"
    also: tuple[int, ...] = ()  # other lines involved (a contradiction has two); left out of the report when empty

    def to_dict(self) -> dict:
        data = asdict(self)
        if not self.also:
            data.pop("also")
        else:
            data["also"] = list(self.also)
        return data


def verdict_for(findings) -> str:
    severities = {f.severity for f in findings}
    if BLOCK in severities:
        return VERDICT_BLOCK
    if WARN in severities:
        return VERDICT_FIX
    return VERDICT_OK


def worst_verdict(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: VERDICT_RANK[v])
