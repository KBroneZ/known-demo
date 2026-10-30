"""Synthetic engines for --mock mode. Output is FAKE and must never be presented as measurement.

Answers are sampled from a made-up visibility model over *fictional* clinics. The point is to
exercise the whole pipeline (storage, extraction, stats, report) without spending money.
"""

from __future__ import annotations

import random
import threading

from ..config import Market
from ..extract import Brand
from .base import Citation, Engine, RawResult, error_result

MODEL = "mock-synthetic-v1"
DIRECTORIES = ["yelp.com", "healthgrades.com", "zocdoc.com", "reddit.com", "lantern.llc", "google.com"]
STYLES = {
    "openai": "Here are well-reviewed options in {city}:\n{items}\nCheck current reviews before booking.",
    "anthropic": "Based on my search, these practices come up for {city}:\n{items}\n"
    "I'd verify insurance and availability directly.",
    "perplexity": "Top results for {city}:\n{items}\nSources: see the listed pages.",
    "google_aio": "Dentists in {city} frequently recommended:\n{items}",
    "google_ai_mode": "In {city}, a few practices stand out:\n{items}\nAsk about financing and first-visit pricing.",
}


class MockEngine(Engine):
    def __init__(self, persona: type[Engine], brands: list[Brand], fillers: list[dict], seed: int = 0) -> None:
        super().__init__(model=MODEL, params={}, client=None)
        self.key = persona.key
        self.label = persona.label + " [MOCK]"
        self.tool_version = "mock"
        self.est_cost_upper = persona.est_cost_upper  # simulated, to exercise the budget guard
        self.brands = brands
        self.fillers = fillers
        self.seed = seed
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return True

    def query(self, prompt: str, market: Market) -> RawResult:
        with self._lock:
            n = self._counts.get(prompt, 0)
            self._counts[prompt] = n + 1
        rng = random.Random(f"{self.seed}|{self.key}|{prompt}|{n}")
        roll = rng.random()
        if roll < 0.03:
            return error_result("mock transient error", retryable=True, http_status=429)
        if roll < 0.04:
            return error_result("mock hard error", retryable=False, http_status=400)
        if self.key == "google_aio" and rng.random() > 0.35:
            return RawResult(answer_text="", answer_present=False, raw={"mock": True, "aio": None})

        pool = [(b.name, b.domains[0] if b.domains else None, self._weight(b.id, prompt)) for b in self.brands]
        pool += [(f["name"], f["domain"], 0.35) for f in self.fillers]
        k = rng.randint(3, 6)
        chosen: list[tuple[str, str | None]] = []
        for _ in range(min(k, len(pool))):
            total = sum(w for _, _, w in pool)
            pick = rng.random() * total
            acc = 0.0
            for idx, (name, dom, w) in enumerate(pool):
                acc += w
                if pick <= acc:
                    chosen.append((name, dom))
                    pool.pop(idx)
                    break
        items = "\n".join(f"{i}. {name}: general and cosmetic care." for i, (name, _) in enumerate(chosen, 1))
        text = STYLES[self.key].format(city=market.city, items=items)
        urls = [f"https://www.{dom}/" for _, dom in chosen if dom and rng.random() < 0.5]
        urls += [f"https://www.{d}/austin-dentists" for d in rng.sample(DIRECTORIES, rng.randint(1, 3))]
        cites = [Citation(u, None, i, "cited") for i, u in enumerate(urls, 1)]
        return RawResult(answer_text=text, citations=cites, raw={"mock": True, "answer": text, "urls": urls})

    def _weight(self, brand_id: str, prompt: str) -> float:
        strength = 0.08 + 0.8 * random.Random(f"{self.seed}|s|{brand_id}").random() ** 1.5
        engine_bias = 0.5 + random.Random(f"{self.seed}|e|{self.key}|{brand_id}").random()
        prompt_affinity = 0.4 + 1.2 * random.Random(f"{self.seed}|p|{prompt}|{brand_id}").random()
        return strength * engine_bias * prompt_affinity
