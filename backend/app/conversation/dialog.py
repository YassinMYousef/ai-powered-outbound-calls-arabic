"""Branching dialog tree for the follow-up call script.

Module: Conversation/NLU. The script pulls in details from the prior inbound
call (ticket ID, procedure steps) and branches on the customer's Arabic reply.

Classification is rule-based so this module stays dependency-free (no API key,
no network). The requirements doc targets a GPT-4 classifier; when that lands,
the phrase tables below become its regression suite.
"""
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    YES = "yes"              # "نعم" — procedure step completed
    NO = "no"                # "لا" — not completed
    UNCERTAIN = "uncertain"  # "غير متأكد"
    AGENT = "agent"          # customer asks for a live agent
    UNKNOWN = "unknown"      # unusable speech — provisional, may be folded into UNCERTAIN


class Action(str, Enum):
    MARK_RESOLVED = "mark_resolved"
    OFFER_HELP = "offer_help"
    TRANSFER_TO_AGENT = "transfer_to_agent"
    REPEAT_QUESTION = "repeat_question"
    END_CALL = "end_call"


@dataclass
class DialogState:
    call_id: int
    ticket_id: str | None = None
    turn: int = 0


# --- Arabic normalization -------------------------------------------------
# Egyptian STT output is orthographically noisy: diacritics come and go, hamza
# carriers vary, and taa marbuta is written both ways. Match on a folded form.

_DIACRITICS = re.compile(r"[ً-ْٰـ]")
_STANDALONE_HAMZA = re.compile("ء")
_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")
_LETTER_FOLDING = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
})


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text)
    text = text.translate(_LETTER_FOLDING)
    text = _STANDALONE_HAMZA.sub("", text)
    text = _PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _pattern(phrase: str, *, definite_article: bool = False) -> re.Pattern[str]:
    """Compile one phrase into a word-bounded matcher.

    Bare substring matching is unusable here: "اه" (yes) occurs inside dozens of
    unrelated words, and "نعم" sits inside "نعمة". Arabic letters are \\w, so the
    lookaround boundaries work.
    """
    prefix = "(?:ال)?" if definite_article else ""
    return re.compile(rf"(?<!\w){prefix}{re.escape(_normalize(phrase))}(?!\w)")


def _compile(*phrases: str, definite_article: bool = False) -> tuple[re.Pattern[str], ...]:
    return tuple(_pattern(p, definite_article=definite_article) for p in phrases)


def _matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


# --- Phrase tables --------------------------------------------------------
# Written in natural orthography and normalized at import; never hand-folded.
# Seeded from .claude/skills/test-call-flow/SKILL.md, widened across Egyptian
# colloquial and MSA registers.

AGENT_WORDS = (
    "عايز أكلم موظف", "عاوز أكلم موظف", "عايزة أكلم موظف", "محتاج أكلم حد",
    "ممكن أكلم حد", "عايز أتكلم مع حد", "حولني لحد", "حولني لموظف",
    "وصلني بموظف", "كلمني مع موظف", "عايز مسؤول", "خدمة العملاء",
    "ممثل خدمة العملاء", "عايز إنسان", "مش عايز أتكلم مع روبوت",
)
UNCERTAIN_WORDS = (
    "غير متأكد", "مش متأكد", "مش متأكدة", "لست متأكدا", "مش عارف", "مش عارفة",
    "معرفش", "ما أعرفش", "لا أعرف", "لا أدري", "مش فاكر", "مش فاكرة",
    "مفتكرش", "ما افتكرش", "مش واضح", "محتار", "ممكن", "يمكن",
)
NO_WORDS = (
    "لا", "لأ", "لاء", "لأه", "لسه", "لسه معملتش", "معملتش", "ما عملتش",
    "معملتهاش", "مقدرتش", "ما قدرتش", "مخلصتش", "ما خلصتش", "مكملتش",
    "ما كملتش", "منفعش", "ما نفعش", "مانفذتش", "مفيش", "مش تمام", "مش عامل",
    "أبدا", "لم أفعل", "لم أكمل", "لم يتم", "غير مكتمل",
)
YES_WORDS = (
    "نعم", "أيوه", "أيوة", "اه", "آه", "تمام", "كله تمام", "ماشي", "حاضر",
    "طبعا", "أكيد", "بالتأكيد", "صح", "صحيح", "مظبوط", "مضبوط", "بالظبط",
    "خلاص", "خلصت", "خلصتها", "عملتها", "عملته", "عملت", "نفذت", "اتعمل",
    "تم", "حصل", "أوكي", "اوك",
)

_AGENT_PHRASES = _compile(*AGENT_WORDS)
_AGENT_REQUEST_VERBS = _compile(
    "عايز", "عاوز", "عايزة", "محتاج", "ممكن", "حولني", "وصلني", "كلمني",
    "أكلم", "اتكلم", "اتحول",
)
_AGENT_PERSON_NOUNS = _compile(
    "موظف", "حد", "مسؤول", "مشرف", "إنسان", "بشري", "ممثل", "خدمة العملاء",
    definite_article=True,
)
_UNCERTAIN_PHRASES = _compile(*UNCERTAIN_WORDS)
_NO_PHRASES = _compile(*NO_WORDS)
_YES_PHRASES = _compile(*YES_WORDS)

# "مش تمام" contains "تمام"; "معملتش" is "عملت" wearing the Egyptian ما…ش
# circumfix. Without this guard a widened YES table swallows negated replies.
_NEGATION_MARKERS = _compile("مش", "لسه", "لم", "لن", "ولا")
# The circumfix written apart ("ما عملتش"). A bare "ما" is not a negation —
# "ما شاء الله" is an exclamation, not a refusal.
_NEGATION_CIRCUMFIX = re.compile(r"(?<!\w)ما\s+\w*ش(?!\w)")


def _is_negated(text: str) -> bool:
    return _matches(text, _NEGATION_MARKERS) or bool(_NEGATION_CIRCUMFIX.search(text))


def _is_agent_request(text: str) -> bool:
    if _matches(text, _AGENT_PHRASES):
        return True
    # A request verb plus a person noun, in any order. Guards against a bare
    # "موظف" — a customer narrating "الموظف قالي..." is not asking for a transfer.
    return _matches(text, _AGENT_REQUEST_VERBS) and _matches(text, _AGENT_PERSON_NOUNS)


def classify_intent(transcript_ar: str) -> Intent:
    """Map raw Arabic STT output to an Intent.

    Precedence is load-bearing: an explicit escalation request must never be
    swallowed by another token in the same utterance, and "لا أعرف" opens with
    the canonical NO particle while meaning UNCERTAIN.
    """
    text = _normalize(transcript_ar)
    if not text:
        return Intent.UNKNOWN
    if _is_agent_request(text):
        return Intent.AGENT
    if _matches(text, _UNCERTAIN_PHRASES):
        return Intent.UNCERTAIN
    if _matches(text, _NO_PHRASES) or _is_negated(text):
        return Intent.NO
    if _matches(text, _YES_PHRASES):
        return Intent.YES
    # Never fall back to YES: a false MARK_RESOLVED corrupts the FCR report.
    return Intent.UNKNOWN


# --- Transitions ----------------------------------------------------------

ESCALATE_TURN = 2  # from this reply onward, every unresolved intent goes to a human

# (turn 0, turn 1). Beyond ESCALATE_TURN the ladder is bypassed entirely.
_LADDER: dict[Intent, tuple[Action, Action]] = {
    Intent.NO: (Action.OFFER_HELP, Action.TRANSFER_TO_AGENT),
    Intent.UNCERTAIN: (Action.REPEAT_QUESTION, Action.OFFER_HELP),
    Intent.UNKNOWN: (Action.REPEAT_QUESTION, Action.REPEAT_QUESTION),
}


def next_action(state: DialogState, intent: Intent) -> Action:
    """Advance the dialog tree one turn. Called from telephony/webhooks.py.

    Pure: the caller owns incrementing state.turn. Every dead end routes to a
    live agent, so END_CALL is never returned here — webhooks hang up after a
    resolution or a completed transfer.
    """
    if intent is Intent.AGENT:
        return Action.TRANSFER_TO_AGENT
    if intent is Intent.YES:
        return Action.MARK_RESOLVED
    turn = max(0, state.turn)
    if turn >= ESCALATE_TURN:
        return Action.TRANSFER_TO_AGENT
    return _LADDER[intent][turn]
