"""Transport-level behaviour of the TEI wrapper.

These paths bit us in live running: a slow CPU embed exceeded the read timeout
and was reported as "server unreachable", sending the operator after a
container that was in fact running fine.
"""
import httpx
import pytest

from app.conversation.rag import embeddings


@pytest.fixture(autouse=True)
def _fresh_client():
    embeddings._client.cache_clear()
    yield
    embeddings._client.cache_clear()


def _mock_client(monkeypatch, handler) -> list[list[str]]:
    """Route the wrapper's httpx.Client through a MockTransport; record batches."""
    batches: list[list[str]] = []

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        import json

        batches.append(json.loads(request.content)["inputs"])
        return handler(request, batches[-1])

    client = httpx.Client(
        transport=httpx.MockTransport(_transport_handler), base_url="http://tei.test"
    )
    monkeypatch.setattr(embeddings, "_client", lambda: client)
    return batches


def test_long_input_is_split_into_small_batches(monkeypatch) -> None:
    batches = _mock_client(
        monkeypatch, lambda req, inputs: httpx.Response(200, json=[[0.1] * 1024] * len(inputs))
    )
    vectors = embeddings.embed_passages([f"chunk {i}" for i in range(10)])

    assert len(vectors) == 10  # order preserved, nothing dropped across batches
    assert all(len(b) <= embeddings._BATCH_SIZE for b in batches)
    assert sum(len(b) for b in batches) == 10


def test_timeout_is_not_reported_as_unreachable(monkeypatch) -> None:
    def _timeout(req, inputs):
        raise httpx.ReadTimeout("timed out", request=req)

    _mock_client(monkeypatch, _timeout)
    with pytest.raises(RuntimeError, match="timed out") as exc:
        embeddings.embed_passages(["نص"])
    assert "unreachable" not in str(exc.value)


def test_connect_error_points_at_the_container(monkeypatch) -> None:
    def _refused(req, inputs):
        raise httpx.ConnectError("connection refused", request=req)

    _mock_client(monkeypatch, _refused)
    with pytest.raises(RuntimeError, match="unreachable"):
        embeddings.embed_passages(["نص"])


def test_http_error_from_tei_propagates(monkeypatch) -> None:
    _mock_client(monkeypatch, lambda req, inputs: httpx.Response(413, text="batch too large"))
    with pytest.raises(httpx.HTTPStatusError):
        embeddings.embed_passages(["نص"])
