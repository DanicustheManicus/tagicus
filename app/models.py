from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SourceResult:
    source: str
    artist: Optional[str] = None
    title: Optional[str] = None
    album: Optional[str] = None
    year: Optional[str] = None
    track: Optional[int] = None
    genre: Optional[str] = None
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)

@dataclass
class FieldVote:
    field_name: str
    best_value: Optional[str] = None
    votes: dict = field(default_factory=dict)
    agreement: float = 0.0
    conflict: bool = False
