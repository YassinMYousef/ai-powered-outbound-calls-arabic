"""Audio format conversion between telephony and STT/TTS formats.

Module: Speech Processing (Sprint 3).

Telephony (Twilio Media Streams) carries 8 kHz mu-law mono; Whisper wants
16 kHz linear-PCM WAV. That exact pair — mu-law <-> PCM and 8k <-> 16k
resampling — is handled natively by the Python standard library (`audioop` +
`wave`), so this module uses stdlib rather than pydub. That deliberately drops
the ffmpeg-on-PATH requirement the pydub route would add: the conversions here
need no external binary, which keeps the call loop and CI dependency-free.

(pydub/ffmpeg remains the tool of choice if we ever need to decode compressed
container formats like mp3 here — e.g. if TTS output isn't already ulaw/PCM.
Prefer requesting ulaw_8000 straight from ElevenLabs to avoid that entirely.)

Note: `audioop` is deprecated for removal in Python 3.13; the project targets
3.11. Revisit with `audioop-lts` or a small codec if we move to 3.13+.
"""
import audioop
import io
import wave

TELEPHONY_RATE = 8000  # Hz — Twilio mu-law
STT_RATE = 16000       # Hz — Whisper input
_SAMPLE_WIDTH = 2      # bytes — 16-bit linear PCM (audioop's mu-law pairing)


def telephony_to_wav(payload: bytes) -> bytes:
    """Convert telephony audio (8 kHz mu-law mono) to 16 kHz mono WAV for STT.

    `payload` is the raw mu-law byte stream (one byte per sample), i.e. Twilio
    Media Stream media payloads already base64-decoded and concatenated.
    """
    if not payload:
        raise ValueError("telephony_to_wav() got empty payload")

    # mu-law -> 16-bit linear PCM, then upsample 8k -> 16k.
    pcm = audioop.ulaw2lin(payload, _SAMPLE_WIDTH)
    pcm, _ = audioop.ratecv(pcm, _SAMPLE_WIDTH, 1, TELEPHONY_RATE, STT_RATE, None)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(_SAMPLE_WIDTH)
        wav.setframerate(STT_RATE)
        wav.writeframes(pcm)
    return buffer.getvalue()


def wav_to_telephony(wav: bytes) -> bytes:
    """Convert a WAV (any rate/width/mono-or-stereo) to 8 kHz mu-law mono bytes.

    Returns the raw mu-law stream telephony expects — hand these bytes to the
    provider's outbound-media channel. (If TTS already emits ulaw_8000, no
    conversion is needed at all.)
    """
    with wave.open(io.BytesIO(wav), "rb") as reader:
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        rate = reader.getframerate()
        frames = reader.readframes(reader.getnframes())

    # Normalize to 16-bit mono, resample to 8 kHz, then encode mu-law.
    if width != _SAMPLE_WIDTH:
        frames = audioop.lin2lin(frames, width, _SAMPLE_WIDTH)
    if channels == 2:
        frames = audioop.tomono(frames, _SAMPLE_WIDTH, 0.5, 0.5)
    elif channels != 1:
        raise ValueError(f"unsupported channel count: {channels}")
    if rate != TELEPHONY_RATE:
        frames, _ = audioop.ratecv(frames, _SAMPLE_WIDTH, 1, rate, TELEPHONY_RATE, None)

    return audioop.lin2ulaw(frames, _SAMPLE_WIDTH)
