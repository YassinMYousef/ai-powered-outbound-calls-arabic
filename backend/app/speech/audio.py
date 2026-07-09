"""Audio format conversion between telephony and STT/TTS formats.

Module: Speech Processing. Telephony streams 8 kHz mu-law; Whisper wants
16 kHz WAV. Uses pydub, which requires ffmpeg on PATH.
"""


def telephony_to_wav(payload: bytes) -> bytes:
    """Convert telephony audio (8 kHz mu-law) to 16 kHz WAV for STT."""
    raise NotImplementedError


def wav_to_telephony(wav: bytes) -> bytes:
    """Convert TTS output to the telephony provider's playback format."""
    raise NotImplementedError
