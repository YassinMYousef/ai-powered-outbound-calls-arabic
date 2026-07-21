"""The unanswered-question (KB gap) log — data module (app/data/kb_gaps.py) and
its admin endpoints (GET /api/kb/gaps, POST /api/kb/gaps/resolve), on SQLite.

`normalized_query` is the grouping key, so `resolve` takes the STORED normalized
form (what list_gaps returns and the frontend passes back), not raw wording. Most
strings below are chosen to normalize to themselves; the two that aren't
(hamza/taa-marbuta variants) exercise the normalization on purpose.
"""
import pytest

from app.config import settings
from app.data import kb_gaps
from app.data.models import UnansweredQuestion


def _record(db, query, reason="no_match", **kwargs):
    kb_gaps.record(db, query=query, reason=reason, **kwargs)
    db.commit()


def _key(db, status="open", index=0):
    """The stored normalized_query of a group, as the review UI would read it."""
    return kb_gaps.list_gaps(db, status=status)[index]["normalized_query"]


# --- record + normalization -------------------------------------------------


def test_record_persists_the_gap_and_its_normalized_key(db_session) -> None:
    _record(db_session, "كيف أفعّل الشريحة؟", reason="no_citation", chunks_retrieved=3, top_similarity=0.7)

    row = db_session.query(UnansweredQuestion).one()
    assert row.query == "كيف أفعّل الشريحة؟"
    assert row.reason == "no_citation"
    assert row.chunks_retrieved == 3
    assert row.top_similarity == 0.7
    assert row.status == "open"
    # Shadda stripped, hamza + taa-marbuta unified — this is the grouping key.
    assert row.normalized_query == "كيف افعل الشريحه"


def test_orthographic_variants_group_into_one_gap(db_session) -> None:
    _record(db_session, "كيف أفعّل الشريحة؟")
    _record(db_session, "كيف افعل الشريحه")  # same question, plain spelling

    groups = kb_gaps.list_gaps(db_session)
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["sample_query"] == "كيف افعل الشريحه"  # newest wording


def test_record_is_skipped_when_logging_disabled(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "kb_gap_logging_enabled", False)
    assert kb_gaps.record(db_session, query="منتج جديد", reason="no_match") is None
    db_session.commit()
    assert db_session.query(UnansweredQuestion).count() == 0


def test_record_ignores_a_non_gap_reason(db_session) -> None:
    # "covered"/"refused" are answer.py verdicts that are not gaps.
    assert kb_gaps.record(db_session, query="منتج جديد", reason="covered") is None
    db_session.commit()
    assert db_session.query(UnansweredQuestion).count() == 0


# --- list (grouped, ranked) -------------------------------------------------


def test_list_gaps_ranks_by_hit_count(db_session) -> None:
    for _ in range(3):
        _record(db_session, "منتج متكرر")  # asked 3x
    _record(db_session, "منتج نادر")  # asked 1x

    groups = kb_gaps.list_gaps(db_session)
    assert [g["count"] for g in groups] == [3, 1]
    assert groups[0]["normalized_query"] == "منتج متكرر"


def test_list_gaps_ranks_by_priority_not_just_count(db_session) -> None:
    # A frequently-asked but merely low-confidence gap vs a rarer total miss:
    # 3 * 0.6 = 1.8 (low_confidence) < 2 * 1.0 = 2.0 (no_match) → the miss ranks first.
    for _ in range(3):
        _record(db_session, "سؤال ضعيف الثقة", reason="low_confidence")
    for _ in range(2):
        _record(db_session, "سؤال بلا نتائج", reason="no_match")

    groups = kb_gaps.list_gaps(db_session)
    assert [g["normalized_query"] for g in groups] == [
        kb_gaps._normalize("سؤال بلا نتائج"),
        kb_gaps._normalize("سؤال ضعيف الثقة"),
    ]
    assert groups[0]["priority"] == 2.0
    assert groups[1]["priority"] == 1.8


def test_list_gaps_reports_the_most_common_reason(db_session) -> None:
    _record(db_session, "منتج", reason="no_match")
    _record(db_session, "منتج", reason="no_match")
    _record(db_session, "منتج", reason="low_confidence")

    group = kb_gaps.list_gaps(db_session)[0]
    assert group["reason"] == "no_match"
    assert group["reasons"] == {"no_match": 2, "low_confidence": 1}


def test_list_gaps_filters_by_status(db_session) -> None:
    _record(db_session, "طلب مفتوح")
    _record(db_session, "طلب محلول")
    kb_gaps.resolve(db_session, normalized_query="طلب محلول", status="resolved")

    assert [g["normalized_query"] for g in kb_gaps.list_gaps(db_session, status="open")] == ["طلب مفتوح"]
    assert [g["normalized_query"] for g in kb_gaps.list_gaps(db_session, status="resolved")] == ["طلب محلول"]


# --- resolve ----------------------------------------------------------------


def test_resolve_flips_every_open_row_in_the_group(db_session) -> None:
    _record(db_session, "كيف أفعّل الشريحة؟")
    _record(db_session, "كيف افعل الشريحه")  # same normalized group

    updated = kb_gaps.resolve(
        db_session, normalized_query=_key(db_session), status="resolved", note="أضفت دليل التفعيل"
    )

    assert updated == 2
    rows = db_session.query(UnansweredQuestion).all()
    assert {r.status for r in rows} == {"resolved"}
    assert all(r.resolved_at is not None and r.resolution_note == "أضفت دليل التفعيل" for r in rows)
    assert kb_gaps.list_gaps(db_session, status="open") == []


def test_resolve_touches_only_the_matching_group(db_session) -> None:
    _record(db_session, "بند اول")
    _record(db_session, "بند ثاني")

    assert kb_gaps.resolve(db_session, normalized_query="بند اول", status="dismissed") == 1
    assert [g["normalized_query"] for g in kb_gaps.list_gaps(db_session, status="open")] == ["بند ثاني"]


def test_resolve_rejects_an_invalid_status(db_session) -> None:
    with pytest.raises(ValueError, match="status must be"):
        kb_gaps.resolve(db_session, normalized_query="منتج", status="open")


def test_recurrence_after_resolve_opens_a_fresh_gap(db_session) -> None:
    _record(db_session, "منتج")
    kb_gaps.resolve(db_session, normalized_query="منتج", status="resolved")
    _record(db_session, "منتج")  # asked again after being marked resolved

    open_groups = kb_gaps.list_gaps(db_session, status="open")
    assert [g["count"] for g in open_groups] == [1]  # the recurrence resurfaces on its own


# --- API surface ------------------------------------------------------------


def test_get_gaps_endpoint_returns_grouped_json(client, db_session) -> None:
    _record(db_session, "منتج", reason="no_match")
    _record(db_session, "منتج", reason="no_match")

    body = client.get("/api/kb/gaps").json()
    assert len(body) == 1
    assert body[0]["count"] == 2
    assert body[0]["reason"] == "no_match"
    assert body[0]["last_seen"] is not None


def test_get_gaps_rejects_an_unknown_status(client) -> None:
    assert client.get("/api/kb/gaps?status=nonsense").status_code == 422


def test_resolve_endpoint_marks_the_group_and_returns_count(client, db_session) -> None:
    _record(db_session, "طلب محلول")
    _record(db_session, "طلب محلول")

    res = client.post(
        "/api/kb/gaps/resolve",
        json={"normalized_query": "طلب محلول", "status": "resolved", "note": "تمت الإضافة"},
    )
    assert res.status_code == 200
    assert res.json() == {"updated": 2}
    assert client.get("/api/kb/gaps").json() == []


def test_resolve_endpoint_rejects_a_non_resolvable_status(client) -> None:
    res = client.post(
        "/api/kb/gaps/resolve", json={"normalized_query": "منتج", "status": "open"}
    )
    assert res.status_code == 422


# --- recheck / close-the-loop -----------------------------------------------


def _fake_retrieve_by_keyword(monkeypatch, covered_keyword: str, high=0.95, low=0.2):
    """Stub retrieval: queries containing `covered_keyword` look well-covered."""
    from app.conversation.rag import retrieve as retrieve_mod

    def fake_retrieve(query, k, vector=None, diagnostics=None):
        if diagnostics is not None:
            diagnostics["top_similarity"] = high if covered_keyword in query else low
        return []

    monkeypatch.setattr(retrieve_mod, "retrieve", fake_retrieve)


def test_recheck_auto_resolves_only_now_covered_gaps(db_session, monkeypatch) -> None:
    _record(db_session, "سؤال مغطى الان")
    _record(db_session, "سؤال لسه ناقص")
    _fake_retrieve_by_keyword(monkeypatch, "مغطى")

    resolved = kb_gaps.recheck_open_gaps(db_session)

    assert resolved == 1
    open_groups = [g["normalized_query"] for g in kb_gaps.list_gaps(db_session, status="open")]
    assert open_groups == [kb_gaps._normalize("سؤال لسه ناقص")]
    # The closed one carries the auto-resolution note.
    resolved_row = (
        db_session.query(UnansweredQuestion)
        .filter(UnansweredQuestion.status == "resolved")
        .one()
    )
    assert "auto-resolved" in resolved_row.resolution_note


def test_recheck_endpoint_requires_admin_and_returns_count(client, db_session, monkeypatch) -> None:
    _record(db_session, "سؤال مغطى الان")
    _fake_retrieve_by_keyword(monkeypatch, "مغطى")

    res = client.post("/api/kb/gaps/recheck")
    assert res.status_code == 200
    assert res.json() == {"resolved": 1}
