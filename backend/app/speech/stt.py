"""Arabic speech-to-text (Whisper API or self-hosted model).

Module: Speech Processing.
Must handle Egyptian Arabic and Modern Standard Arabic; accuracy is validated
against real test-call recordings before the dialog module consumes output.
"""


def transcribe(audio_wav: bytes, language: str = "ar") -> str:
    """Transcribe call audio (16 kHz WAV) to Arabic text."""
    raise NotImplementedError
