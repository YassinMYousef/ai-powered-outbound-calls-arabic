"""Lexical (Okapi BM25) scoring over KB chunk text, Arabic-aware.

Module: Conversation/RAG. Postgres ships no Arabic text-search config (no
stemmer, no stopwords), so the lexical arm runs in-process instead of in SQL:
light Arabic normalization — diacritics/tatweel stripped, alef/yaa/hamza/taa
marbuta variants unified — then plain Okapi BM25. Pure functions over the
corpus the caller passes in; no I/O here.
"""
import math
import re

# Okapi BM25 constants — the standard defaults from the literature.
_K1 = 1.5
_B = 0.75

# Tashkeel (U+064B–U+065F), dagger alef (U+0670), and tatweel (U+0640) carry no
# lexical meaning and appear inconsistently across KB documents and queries.
# Kept as explicit code points: a literal 064B–0670 range would also swallow
# the Arabic-Indic digits (U+0660–0669) sitting between them.
_STRIP = re.compile(r"[\u064b-\u065f\u0670\u0640]")

# Orthographic variants written interchangeably in real-world Arabic text.
_UNIFY = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه"}
)


def tokenize(text: str) -> list[str]:
    """Normalized word tokens; Arabic variants unified so surface forms match."""
    return re.findall(r"\w+", _STRIP.sub("", text).translate(_UNIFY).lower())


def rank(query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
    """BM25-rank `texts` against `query` — (index, score) pairs, best first.

    Only positive scores are returned: a chunk sharing no term with the query
    is not a lexical match at all, not a weak one.
    """
    corpus = [tokenize(text) for text in texts]
    query_terms = set(tokenize(query))
    if not query_terms or not corpus:
        return []

    n = len(corpus)
    avgdl = sum(len(doc) for doc in corpus) / n
    df: dict[str, int] = {}
    for doc in corpus:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    scores = [0.0] * n
    for term in query_terms:
        term_df = df.get(term)
        if not term_df:
            continue
        idf = math.log(1 + (n - term_df + 0.5) / (term_df + 0.5))
        for i, doc in enumerate(corpus):
            tf = doc.count(term)
            if not tf:
                continue
            norm = tf + _K1 * (1 - _B + _B * len(doc) / avgdl) if avgdl else tf
            scores[i] += idf * tf * (_K1 + 1) / norm

    ranked = sorted(((i, s) for i, s in enumerate(scores) if s > 0), key=lambda pair: -pair[1])
    return ranked[:top_n]
