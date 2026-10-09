from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import Utterance, Word

DiarizationTurn = tuple[float, float, str]


def _overlap(start: float, end: float, turn: DiarizationTurn) -> float:
    return max(0.0, min(end, turn[1]) - max(start, turn[0]))


def assign_speakers(words: Iterable[Word], turns: Sequence[DiarizationTurn]) -> list[Word]:
    """Assign each ASR word to the speaker with the greatest temporal overlap."""
    assigned: list[Word] = []
    for word in words:
        speaker: str | None = None
        best_overlap = 0.0
        for turn in turns:
            overlap = _overlap(word.start, word.end, turn)
            if overlap > best_overlap:
                best_overlap = overlap
                speaker = turn[2]
        if speaker is None and turns:
            midpoint = (word.start + word.end) / 2
            nearest = min(turns, key=lambda turn: abs(midpoint - (turn[0] + turn[1]) / 2))
            speaker = nearest[2]
        assigned.append(
            Word(
                start=word.start,
                end=word.end,
                text=word.text,
                speaker=speaker or "UNKNOWN",
                probability=word.probability,
            )
        )
    return assigned


def group_utterances(words: Sequence[Word], max_gap: float = 1.25) -> list[Utterance]:
    groups: list[list[Word]] = []
    for word in words:
        if not groups:
            groups.append([word])
            continue
        previous = groups[-1][-1]
        if word.speaker != previous.speaker or word.start - previous.end > max_gap:
            groups.append([word])
        else:
            groups[-1].append(word)

    utterances = [
        Utterance(
            start=group[0].start,
            end=group[-1].end,
            speaker=group[0].speaker or "UNKNOWN",
            text="".join(word.text for word in group).strip(),
            words=list(group),
        )
        for group in groups
        if "".join(word.text for word in group).strip()
    ]
    return [
        Utterance(
            start=utterance.start,
            end=utterance.end,
            speaker=utterance.speaker,
            text=utterance.text,
            words=utterance.words,
            id=index,
        )
        for index, utterance in enumerate(utterances, start=1)
    ]
