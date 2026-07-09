"""Top-K retrieval from the vector DB for an Arabic query.

Module: Conversation/RAG.
"""


def retrieve(query_ar: str, top_k: int = 5) -> list[dict]:
    """Return matching chunks with scores and source metadata (doc title, page).

    Source metadata must survive to the final answer — citations are a hard
    requirement for the agent chatbot.
    """
    raise NotImplementedError
