"""YAML config loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .extract import Brand


@dataclass(frozen=True)
class Market:
    city: str
    region: str
    country: str
    timezone: str
    lat: float
    lng: float
    dfs_location_name: str  # DataForSEO location_name, e.g. "Austin,Texas,United States"

    @property
    def label(self) -> str:
        return f"{self.city}, {self.region}, {self.country}"


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str


@dataclass(frozen=True)
class Config:
    name: str
    market: Market
    brands: tuple[Brand, ...]
    prompts: tuple[Prompt, ...]
    repetitions: int
    budget_usd: float
    engines: dict[str, dict] = field(default_factory=dict)
    notes: str = ""
    mock: dict = field(default_factory=dict)  # fictional fillers for --mock
    public_notes: str = ""  # replaces `notes` in anonymized output


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    m = data["market"]
    market = Market(
        city=m["city"],
        region=m["region"],
        country=m["country"],
        timezone=m["timezone"],
        lat=float(m["lat"]),
        lng=float(m["lng"]),
        dfs_location_name=m["dfs_location_name"],
    )
    brands = tuple(
        Brand(
            id=b["id"],
            name=b["name"],
            aliases=tuple(b.get("aliases", [])),
            domains=tuple(b.get("domains", [])),
            public_id=b.get("public_id"),
            public_name=b.get("public_name"),
            public_domain=b.get("public_domain"),
        )
        for b in data["brands"]
    )
    prompts = tuple(Prompt(id=p["id"], text=p["text"]) for p in data["prompts"])
    ids = [b.id for b in brands]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate brand ids in config")
    return Config(
        name=data["name"],
        market=market,
        brands=brands,
        prompts=prompts,
        repetitions=int(data.get("repetitions", 5)),
        budget_usd=float(data.get("budget_usd", 25)),
        engines=data.get("engines", {}),
        notes=data.get("notes", ""),
        mock=data.get("mock", {}),
        public_notes=data.get("public_notes", ""),
    )
