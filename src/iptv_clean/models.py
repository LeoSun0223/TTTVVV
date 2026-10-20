from dataclasses import dataclass, field
from typing import Dict, List


class Rejected(Exception):
    """Machine-readable failure. Never embed an upstream URL or response body."""

    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(code)


@dataclass
class Candidate:
    channel: str
    url: str
    sources: List[str] = field(default_factory=list)
    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class Response:
    url: str
    body: bytes
    status: int = 200
    headers: dict = field(default_factory=dict)
    ips: List[str] = field(default_factory=list)
    elapsed: float = 0.0
    ttfb: float = 0.0
