"""Arabic text-to-speech — natural-sounding neural voices.

Module: Speech Processing. Provider selection is pending (candidates need
Arabic voice samples evaluated); keep all provider calls behind synthesize()
so swapping providers touches only this file.
"""


def synthesize(text_ar: str, voice: str | None = None) -> bytes:
    """Render Arabic text to audio suitable for telephony playback.

    Used for the dynamic greeting (ticket details from the prior inbound call
    are interpolated into the script) and for every dialog turn.
    """
    raise NotImplementedError
