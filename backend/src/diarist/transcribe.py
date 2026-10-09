from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Any

from .alignment import DiarizationTurn, assign_speakers, group_utterances
from .audio import duration_seconds, normalize_audio, validate_audio
from .devices import (
    resolve_diarization_device,
    resolve_whisper_backend,
    resolve_whisper_compute_type,
    resolve_whisper_device,
)
from .languages import is_supported, normalize
from .models import Transcript, Word

# mlx-community publishes MLX-converted weights under a different repo
# naming convention than faster-whisper's CTranslate2 model shorthands.
DEFAULT_WHISPER_MODELS = {
    "faster-whisper": "large-v3",
    "mlx": "mlx-community/whisper-large-v3-mlx",
}
DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"


class TranscriptionError(RuntimeError):
    pass


def _faster_whisper_words(segments: Any) -> list[Word]:
    words: list[Word] = []
    for segment in segments:
        segment_words = getattr(segment, "words", None) or []
        if segment_words:
            for item in segment_words:
                words.append(
                    Word(
                        start=float(item.start),
                        end=float(item.end),
                        text=str(item.word),
                        probability=(
                            float(item.probability) if item.probability is not None else None
                        ),
                    )
                )
        elif str(segment.text or "").strip():
            words.append(
                Word(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=" " + str(segment.text).strip(),
                )
            )
    return words


def _mlx_whisper_words(result: dict[str, Any]) -> list[Word]:
    words: list[Word] = []
    for segment in result.get("segments", []):
        segment_words = segment.get("words") or []
        if segment_words:
            for item in segment_words:
                words.append(
                    Word(
                        start=float(item["start"]),
                        end=float(item["end"]),
                        text=str(item["word"]),
                        probability=(
                            float(item["probability"])
                            if item.get("probability") is not None
                            else None
                        ),
                    )
                )
        elif str(segment.get("text", "")).strip():
            words.append(
                Word(
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                    text=" " + str(segment["text"]).strip(),
                )
            )
    return words


def _diarization_turns(output: Any) -> list[DiarizationTurn]:
    annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = output.speaker_diarization
    return [
        (float(turn.start), float(turn.end), str(speaker))
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]


def _load_pcm16_waveform(path: Path, torch: Any) -> dict[str, Any]:
    """Load our normalized WAV without TorchCodec or FFmpeg shared libraries."""
    import numpy as np

    with wave.open(str(path), "rb") as audio:
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
        sample_rate = audio.getframerate()
        frames = audio.readframes(audio.getnframes())
    if channels != 1 or sample_width != 2:
        raise TranscriptionError("Internal audio normalization did not produce mono PCM16 WAV.")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    return {"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": sample_rate}


class TranscriptionEngine:
    """Holds warm Whisper and pyannote models so repeated jobs skip reloading.

    Model weights are cached on disk (HF_HOME, see Dockerfile/deployment) so
    only the very first job after a fresh cache pays the download cost.
    Keeping the loaded models in memory across jobs additionally skips GPU
    weight upload on every request.

    Every device/backend choice below defaults to "auto" (see .devices) and
    can be overridden with an explicit constructor argument or environment
    variable. The one choice auto-detection *cannot* make for you: MLX
    (Apple Silicon/Metal) only works when this process runs natively on
    macOS. It is never available inside Docker, on any host, because Docker
    Desktop's Linux VM has no Metal passthrough. faster-whisper (CUDA or
    CPU) is the only Whisper backend usable in a container.
    """

    def __init__(
        self,
        *,
        whisper_backend: str | None = None,
        whisper_model: str | None = None,
        whisper_device: str | None = None,
        whisper_compute_type: str | None = None,
        diarization_model: str = DEFAULT_DIARIZATION_MODEL,
        diarization_device: str | None = None,
        hf_token: str | None = None,
    ) -> None:
        self.whisper_backend = whisper_backend or resolve_whisper_backend()
        if self.whisper_backend not in DEFAULT_WHISPER_MODELS:
            raise TranscriptionError(
                f"Unknown whisper backend {self.whisper_backend!r}; "
                "expected 'mlx' or 'faster-whisper'."
            )
        self.whisper_model_name = whisper_model or os.getenv(
            "WHISPER_MODEL", DEFAULT_WHISPER_MODELS[self.whisper_backend]
        )
        if self.whisper_backend == "faster-whisper":
            self.whisper_device = whisper_device or resolve_whisper_device()
            self.whisper_compute_type = whisper_compute_type or resolve_whisper_compute_type(
                self.whisper_device
            )
        else:
            # mlx-whisper always runs on the GPU/ANE via Metal; there is no
            # device or compute-type knob to turn.
            self.whisper_device = None
            self.whisper_compute_type = None
        self.diarization_model_name = diarization_model
        self.diarization_device = diarization_device or resolve_diarization_device()
        self.hf_token = hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
        self._whisper: Any = None
        self._diarization: Any = None

    @property
    def whisper(self) -> Any:
        if self._whisper is None:
            if self.whisper_backend == "mlx":
                try:
                    import mlx_whisper
                except ImportError as exc:
                    raise TranscriptionError(
                        "WHISPER_BACKEND=mlx requires mlx-whisper, which only installs on "
                        "Apple Silicon macOS. Install it with `uv sync --extra mlx` and run "
                        "the backend natively -- this never works inside Docker. To use "
                        "Docker on a Mac, unset WHISPER_BACKEND (or set it to "
                        "faster-whisper) and accept CPU-speed transcription."
                    ) from exc
                self._whisper = mlx_whisper
            else:
                from faster_whisper import WhisperModel

                self._whisper = WhisperModel(
                    self.whisper_model_name,
                    device=self.whisper_device,
                    compute_type=self.whisper_compute_type,
                )
        return self._whisper

    @property
    def diarization(self) -> Any:
        if self._diarization is None:
            import torch
            from pyannote.audio import Pipeline

            diarization_is_local = Path(self.diarization_model_name).expanduser().exists()
            if not self.hf_token and not diarization_is_local:
                raise TranscriptionError(
                    "Set HF_TOKEN (pyannote Community-1 requires a Hugging Face read token)."
                )
            try:
                pipeline = Pipeline.from_pretrained(
                    self.diarization_model_name, token=self.hf_token
                )
                if pipeline is None:
                    raise RuntimeError("pipeline loader returned no pipeline")
            except Exception as exc:
                raise TranscriptionError(
                    "Could not load the diarization model. Accept its Hugging Face conditions "
                    "and check HF_TOKEN."
                ) from exc
            pipeline.to(torch.device(self.diarization_device))
            self._diarization = pipeline
        return self._diarization

    def transcribe(
        self,
        source: Path,
        *,
        num_speakers: int | None = None,
        language: str | None = None,
        initial_prompt: str | None = None,
        work_dir: Path,
    ) -> Transcript:
        import torch

        if language is not None and not is_supported(language):
            raise TranscriptionError(f"Unsupported language code: {language!r}")
        requested_language = language
        whisper_language = normalize(language)

        source = validate_audio(source)
        normalized = work_dir / "audio-16khz-mono.wav"
        normalize_audio(source, normalized)

        if self.whisper_backend == "mlx":
            result = self.whisper.transcribe(
                str(normalized),
                path_or_hf_repo=self.whisper_model_name,
                language=whisper_language,
                task="transcribe",
                word_timestamps=True,
                initial_prompt=initial_prompt,
                verbose=False,
            )
            words = _mlx_whisper_words(result)
            detected_language = str(result.get("language") or whisper_language or "en")
        else:
            segments, info = self.whisper.transcribe(
                str(normalized),
                language=whisper_language,
                task="transcribe",
                word_timestamps=True,
                initial_prompt=initial_prompt,
            )
            words = _faster_whisper_words(segments)
            detected_language = str(info.language)

        diarization_kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        diarization = self.diarization(
            _load_pcm16_waveform(normalized, torch),
            **diarization_kwargs,
        )

        assigned_words = assign_speakers(words, _diarization_turns(diarization))
        utterances = group_utterances(assigned_words)
        speakers = sorted({utterance.speaker for utterance in utterances})
        return Transcript(
            source=source,
            language=detected_language,
            requested_language=requested_language,
            duration=duration_seconds(normalized),
            model=f"{self.whisper_backend}:{self.whisper_model_name}",
            diarization_model=self.diarization_model_name,
            requested_speakers=num_speakers,
            speakers=speakers,
            utterances=utterances,
        )
