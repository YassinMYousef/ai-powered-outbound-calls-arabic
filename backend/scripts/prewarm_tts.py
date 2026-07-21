"""Pre-generate ("download") audio for the static call phrases.

The greeting and closing/transfer/offer lines never change per call, so playing
them should never cost a live ElevenLabs round-trip — that dead air is what the
caller hears as the greeting "loading" or a long pause before the closing
message. This synthesizes each static phrase once into the on-disk cache
(app/data/assets/tts) that telephony/audio_store.get_cached_audio serves from.

Run this once after setup, and again with --force after changing the voice,
model, or output format (those are part of the cache key).

Usage (from backend/, venv active, TTS_API_KEY set):
    python scripts/prewarm_tts.py
    python scripts/prewarm_tts.py --force
"""
import argparse
import sys

from app.speech.replies import static_phrases
from app.telephony.audio_store import prewarm_disk_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-generate static call audio.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-synthesize even phrases already cached on disk",
    )
    args = parser.parse_args()

    phrases = static_phrases()
    try:
        written = prewarm_disk_cache(phrases, force=args.force)
    except Exception as exc:  # surface config/provider errors as a clean message
        print(f"prewarm failed: {exc}", file=sys.stderr)
        return 1

    skipped = len(phrases) - written
    print(f"pre-generated {written} phrase(s), {skipped} already cached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
