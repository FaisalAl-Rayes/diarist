import json
import zipfile
from pathlib import Path

from diarist.models import Transcript, Utterance, Word
from diarist.output import format_timestamp, read_json, write_docx, write_json


def sample_transcript(tmp_path: Path) -> Transcript:
    word = Word(1.2, 1.8, " Hello", "SPEAKER_00", 0.98)
    return Transcript(
        source=tmp_path / "meeting.m4a",
        language="en",
        requested_language=None,
        duration=65.2,
        model="large-v3",
        diarization_model="pyannote/speaker-diarization-community-1",
        requested_speakers=2,
        speakers=["SPEAKER_00"],
        utterances=[Utterance(1.2, 1.8, "SPEAKER_00", "Hello", [word], id=1)],
    )


def test_timestamp() -> None:
    assert format_timestamp(3661.9) == "01:01:01"


def test_writes_utf8_json_and_valid_docx(tmp_path: Path) -> None:
    transcript = sample_transcript(tmp_path)
    json_path = tmp_path / "out.json"
    docx_path = tmp_path / "out.docx"

    write_json(transcript, json_path)
    write_docx(transcript, docx_path)

    data = json.loads(json_path.read_text())
    assert data["schema_version"] == "2.0"
    assert data["utterances"][0]["text"] == "Hello"
    assert data["language"] == "en"
    assert data["requested_language"] is None
    assert zipfile.is_zipfile(docx_path)

    restored = read_json(json_path)
    assert restored.source == transcript.source
    assert restored.utterances == transcript.utterances


def test_docx_contains_speaker_and_text(tmp_path: Path) -> None:
    from docx import Document

    transcript = sample_transcript(tmp_path)
    path = tmp_path / "out.docx"

    write_docx(transcript, path)

    text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    assert "SPEAKER_00" in text
    assert "Hello" in text
