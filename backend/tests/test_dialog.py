import pytest

from app.conversation.dialog import (
    ESCALATE_TURN,
    NO_WORDS,
    UNCERTAIN_WORDS,
    YES_WORDS,
    Action,
    DialogState,
    Intent,
    classify_intent,
    next_action,
)

# --- classification -------------------------------------------------------


@pytest.mark.parametrize(
    "transcript",
    ["نعم", "أيوه", "اه تمام", "اتحلت المشكلة", "المشكلة انحلت", "اتصلحت خلاص"],
)
def test_classify_yes_variants(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.YES


@pytest.mark.parametrize("transcript", ["لسه ما اتحلتش", "المشكلة ما اتصلحتش"])
def test_classify_negated_solved_is_no(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.NO


@pytest.mark.parametrize("transcript", ["لا", "لأ", "لسه معملتش"])
def test_classify_no_variants(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.NO


@pytest.mark.parametrize("transcript", ["غير متأكد", "مش متأكد", "مش عارف"])
def test_classify_uncertain_variants(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.UNCERTAIN


@pytest.mark.parametrize("transcript", ["عايز أكلم موظف", "حولني لحد"])
def test_classify_agent_variants(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.AGENT


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [("نَعَم", Intent.YES), ("لأ", Intent.NO), ("لاء", Intent.NO)],
)
def test_classify_normalizes_diacritics_and_alef(transcript: str, expected: Intent) -> None:
    assert classify_intent(transcript) is expected


def test_classify_agent_beats_other_intents() -> None:
    assert classify_intent("مش متأكد عايز أكلم موظف") is Intent.AGENT


def test_classify_agent_by_cooccurrence() -> None:
    # "ممكن" is also an UNCERTAIN token; paired with a person noun it is a transfer request.
    assert classify_intent("ممكن أكلم حد") is Intent.AGENT


def test_classify_bare_person_noun_is_not_agent() -> None:
    assert classify_intent("الموظف قالي أعمل كذا") is not Intent.AGENT


@pytest.mark.parametrize("transcript", ["لا مش متأكد", "لا أعرف"])
def test_classify_uncertain_beats_no(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.UNCERTAIN


@pytest.mark.parametrize("transcript", ["مش تمام", "معملتش"])
def test_classify_negation_guard_blocks_yes(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.NO


@pytest.mark.parametrize("transcript", ["", "   ", "الجو حر النهاردة"])
def test_classify_unknown_for_empty_and_noise(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.UNKNOWN


def test_classify_bare_maa_is_not_negation() -> None:
    # Negation is the ما…ش circumfix; "ما شاء الله" is an exclamation, not a refusal.
    assert classify_intent("ما شاء الله") is not Intent.NO


@pytest.mark.parametrize("transcript", ["ما عملتش", "ما خلصتش"])
def test_classify_split_circumfix_negation_is_no(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.NO


@pytest.mark.parametrize("transcript", ["نعمة", "اهلا"])
def test_classify_respects_word_boundaries(transcript: str) -> None:
    assert classify_intent(transcript) is not Intent.YES


@pytest.mark.parametrize("transcript", YES_WORDS)
def test_classify_every_yes_phrase(transcript: str) -> None:
    assert classify_intent(transcript) is Intent.YES


@pytest.mark.parametrize("transcript", NO_WORDS + UNCERTAIN_WORDS)
def test_classify_never_returns_yes_for_any_no_or_uncertain_phrase(transcript: str) -> None:
    # A false MARK_RESOLVED silently corrupts the FCR report — the product's whole output.
    assert classify_intent(transcript) is not Intent.YES


# --- transitions ----------------------------------------------------------


def _state(turn: int) -> DialogState:
    return DialogState(call_id=1, ticket_id="T-1", turn=turn)


@pytest.mark.parametrize("turn", range(4))
def test_next_action_yes_always_marks_resolved(turn: int) -> None:
    assert next_action(_state(turn), Intent.YES) is Action.MARK_RESOLVED


@pytest.mark.parametrize("turn", range(4))
def test_next_action_agent_always_transfers(turn: int) -> None:
    assert next_action(_state(turn), Intent.AGENT) is Action.TRANSFER_TO_AGENT


def test_next_action_no_offers_help_then_transfers() -> None:
    assert next_action(_state(0), Intent.NO) is Action.OFFER_HELP
    assert next_action(_state(1), Intent.NO) is Action.TRANSFER_TO_AGENT
    assert next_action(_state(2), Intent.NO) is Action.TRANSFER_TO_AGENT


def test_next_action_uncertain_repeats_then_offers_then_transfers() -> None:
    assert next_action(_state(0), Intent.UNCERTAIN) is Action.REPEAT_QUESTION
    assert next_action(_state(1), Intent.UNCERTAIN) is Action.OFFER_HELP
    assert next_action(_state(2), Intent.UNCERTAIN) is Action.TRANSFER_TO_AGENT


def test_next_action_unknown_repeats_twice_then_transfers() -> None:
    assert next_action(_state(0), Intent.UNKNOWN) is Action.REPEAT_QUESTION
    assert next_action(_state(1), Intent.UNKNOWN) is Action.REPEAT_QUESTION
    assert next_action(_state(2), Intent.UNKNOWN) is Action.TRANSFER_TO_AGENT


@pytest.mark.parametrize("turn", range(6))
@pytest.mark.parametrize("intent", list(Intent))
def test_next_action_never_returns_end_call(intent: Intent, turn: int) -> None:
    assert next_action(_state(turn), intent) is not Action.END_CALL


@pytest.mark.parametrize("intent", list(Intent))
def test_next_action_does_not_mutate_state(intent: Intent) -> None:
    state = _state(ESCALATE_TURN - 1)
    next_action(state, intent)
    assert state.turn == ESCALATE_TURN - 1
    assert state.ticket_id == "T-1"
