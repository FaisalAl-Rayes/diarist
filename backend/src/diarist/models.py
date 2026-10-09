from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str
    speaker: str | None = None
    probability: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class Utterance:
    start: float
    end: float
    speaker: str
    text: str
    words: list[Word] = field(default_factory=list)
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker": self.speaker,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }


@dataclass(frozen=True)
class Transcript:
    source: Path
    language: str
    requested_language: str | None
    duration: float
    model: str
    diarization_model: str
    requested_speakers: int | None
    speakers: list[str]
    utterances: list[Utterance]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "2.0",
            "source": str(self.source),
            "language": self.language,
            "requested_language": self.requested_language,
            "duration": round(self.duration, 3),
            "models": {"transcription": self.model, "diarization": self.diarization_model},
            "requested_speakers": self.requested_speakers,
            "speakers": self.speakers,
            "utterances": [utterance.to_dict() for utterance in self.utterances],
        }
