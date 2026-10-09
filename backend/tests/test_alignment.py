import wave

import numpy as np
import torch

from diarist.alignment import assign_speakers, group_utterances
from diarist.models import Word
from diarist.transcribe import _load_pcm16_waveform


def test_assigns_by_largest_overlap_and_groups() -> None:
    words = [
        Word(0.0, 0.8, " Bonjour"),
        Word(0.8, 1.2, " Marie"),
        Word(1.3, 1.8, " Salut"),
    ]
    turns = [(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")]

    assigned = assign_speakers(words, turns)
    utterances = group_utterances(assigned)

    assert [word.speaker for word in assigned] == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]
    assert [utterance.text for utterance in utterances] == ["Bonjour Marie", "Salut"]
    assert [utterance.id for utterance in utterances] == [1, 2]


def test_nearest_turn_fallback_for_word_in_silence() -> None:
    assigned = assign_speakers(
        [Word(2.0, 2.2, " ensuite")],
        [(0.0, 1.0, "SPEAKER_00"), (3.0, 4.0, "SPEAKER_01")],
    )
    assert assigned[0].speaker == "SPEAKER_01"


def test_loads_normalized_wave_without_torchcodec(tmp_path) -> None:
    path = tmp_path / "normalized.wav"
    samples = np.array([-32768, 0, 16384, 32767], dtype="<i2")
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(samples.tobytes())

    loaded = _load_pcm16_waveform(path, torch)

    assert loaded["sample_rate"] == 16000
    assert loaded["waveform"].shape == (1, 4)
    assert torch.isclose(loaded["waveform"][0, 2], torch.tensor(0.5))
