"""Speech audio conversion (Sprint 3) — mu-law <-> WAV, stdlib only (no ffmpeg)."""
import audioop
import io
import wave

import pytest

from app.speech import audio


def _make_wav(pcm: bytes, *, channels=1, width=2, rate=16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _read_wav(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as wav:
        return {
            "channels": wav.getnchannels(),
            "width": wav.getsampwidth(),
            "rate": wav.getframerate(),
            "frames": wav.readframes(wav.getnframes()),
        }


def test_telephony_to_wav_produces_16k_mono_pcm() -> None:
    # 8 kHz mu-law payload: one second of a low-amplitude ramp.
    pcm_8k = b"".join(int(200 * ((i % 40) - 20)).to_bytes(2, "little", signed=True)
                      for i in range(8000))
    mulaw = audioop.lin2ulaw(pcm_8k, 2)

    out = audio.telephony_to_wav(mulaw)
    meta = _read_wav(out)

    assert meta["channels"] == 1
    assert meta["width"] == 2
    assert meta["rate"] == 16000
    # Upsample 8k -> 16k roughly doubles the sample count.
    assert meta["frames"] and len(meta["frames"]) > len(pcm_8k)


def test_telephony_to_wav_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        audio.telephony_to_wav(b"")


def test_wav_to_telephony_returns_mulaw() -> None:
    pcm = b"".join(int(500 * ((i % 20) - 10)).to_bytes(2, "little", signed=True)
                   for i in range(16000))
    wav = _make_wav(pcm, rate=16000)

    mulaw = audio.wav_to_telephony(wav)

    # 16k -> 8k downsample => ~half the sample count, mu-law is one byte/sample.
    assert 0 < len(mulaw) < 16000
    # Decodes back to valid linear PCM without error.
    assert audioop.ulaw2lin(mulaw, 2)


def test_wav_to_telephony_handles_stereo_8bit_and_odd_rate() -> None:
    # 8-bit stereo at 44.1 kHz — must be normalized to 16-bit mono 8 kHz mu-law.
    stereo_8bit = bytes([128, 130] * 4410)  # 4410 stereo frames, 1 byte/sample
    wav = _make_wav(stereo_8bit, channels=2, width=1, rate=44100)

    mulaw = audio.wav_to_telephony(wav)

    assert mulaw  # no exception, non-empty
    assert audioop.ulaw2lin(mulaw, 2)


def test_round_trip_preserves_rate_and_mono() -> None:
    pcm_8k = b"".join(int(300 * ((i % 30) - 15)).to_bytes(2, "little", signed=True)
                      for i in range(8000))
    mulaw_in = audioop.lin2ulaw(pcm_8k, 2)

    wav = audio.telephony_to_wav(mulaw_in)
    mulaw_out = audio.wav_to_telephony(wav)

    # Back to an 8 kHz-length mu-law stream (round-trip through 16 kHz WAV).
    assert abs(len(mulaw_out) - len(mulaw_in)) <= 2


def test_wav_to_stt_wav_converts_8k_mono_to_16k_mono() -> None:
    pcm = b"\x00\x00" * 8000

    converted = audio.wav_to_stt_wav(_make_wav(pcm, rate=8000))
    meta = _read_wav(converted)

    assert meta["channels"] == 1
    assert meta["width"] == 2
    assert meta["rate"] == 16000
    assert meta["frames"]


def test_wav_to_stt_wav_normalizes_44k_stereo() -> None:
    stereo_pcm = b"\x00\x00\x10\x00" * 4410

    converted = audio.wav_to_stt_wav(
        _make_wav(stereo_pcm, channels=2, width=2, rate=44100)
    )
    meta = _read_wav(converted)

    assert meta["channels"] == 1
    assert meta["width"] == 2
    assert meta["rate"] == 16000
    assert meta["frames"]


def test_wav_to_stt_wav_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        audio.wav_to_stt_wav(b"")
