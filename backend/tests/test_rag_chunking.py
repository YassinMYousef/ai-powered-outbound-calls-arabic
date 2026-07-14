import pytest

from app.conversation.rag.chunking import chunk_text


def test_empty_and_whitespace_return_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  \n") == []


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("مرحبا بكم في مركز الاتصال") == ["مرحبا بكم في مركز الاتصال"]


def test_small_paragraphs_pack_into_one_chunk() -> None:
    text = "الفقرة الأولى.\n\nالفقرة الثانية."
    assert chunk_text(text, chunk_size=100, overlap=10) == [text]


def test_chunks_never_exceed_chunk_size() -> None:
    paragraphs = [f"paragraph {i} " + "كلمة " * 30 for i in range(20)]
    chunks = chunk_text("\n\n".join(paragraphs), chunk_size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_hard_split_overlaps_consecutive_pieces() -> None:
    paragraph = "".join(chr(ord("a") + i % 26) for i in range(250))  # no blank lines
    chunks = chunk_text(paragraph, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-20:] == nxt[:20]


def test_packed_chunks_seed_overlap_from_previous_chunk() -> None:
    para1 = "أ" * 90
    para2 = "ب" * 60
    chunks = chunk_text(f"{para1}\n\n{para2}", chunk_size=100, overlap=20)
    assert chunks[0] == para1
    assert chunks[1].startswith(para1[-20:])
    assert chunks[1].endswith(para2)


def test_all_paragraph_content_survives_chunking() -> None:
    paragraphs = [f"إجراء رقم {i}: يرجى تحديث بيانات العميل عبر النظام الداخلي." for i in range(30)]
    chunks = chunk_text("\n\n".join(paragraphs), chunk_size=150, overlap=30)
    joined = "\n".join(chunks)
    assert all(p in joined for p in paragraphs)


def test_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("نص", chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("نص", chunk_size=100, overlap=-1)


def test_oversized_paragraph_splits_on_sentence_boundaries() -> None:
    sentences = [f"الجملة رقم {i} تشرح إجراء تحديث بيانات العميل." for i in range(12)]
    text = " ".join(sentences)  # one paragraph, no blank lines
    chunks = chunk_text(text, chunk_size=120, overlap=30)
    assert len(chunks) > 1
    assert all(c.endswith(".") for c in chunks)  # never cut mid-sentence
    joined = " ".join(chunks)
    assert all(s in joined for s in sentences)


def test_arabic_terminal_punctuation_is_a_sentence_boundary() -> None:
    text = "هل أكملت الإجراء المطلوب؟ نعم تم الإكمال بنجاح. شكراً لتعاونكم معنا."
    chunks = chunk_text(text, chunk_size=40, overlap=0)
    assert chunks[0] == "هل أكملت الإجراء المطلوب؟"
    assert chunks[1] == "نعم تم الإكمال بنجاح."


def test_overlap_seed_starts_on_a_word_boundary() -> None:
    para1 = ("كلمة " * 17).strip()  # 84 chars, raw 23-char tail opens mid-word
    para2 = ("بيان " * 6).strip()
    chunks = chunk_text(f"{para1}\n\n{para2}", chunk_size=90, overlap=23)
    assert chunks[0] == para1
    seed = chunks[1].split("\n\n")[0]
    assert para1.endswith(seed)  # a true suffix of the previous chunk...
    assert set(seed.split()) == {"كلمة"}  # ...made of whole words only


def test_single_newline_list_splits_between_items() -> None:
    items = [f"- خطوة {i}: تأكيد رقم الهاتف مع العميل" for i in range(10)]
    text = "\n".join(items)  # one blank-line paragraph, far over chunk_size
    chunks = chunk_text(text, chunk_size=80, overlap=0)
    assert len(chunks) > 1
    for chunk in chunks:
        assert all(line in items for line in chunk.split("\n"))


def test_mixed_structure_never_exceeds_chunk_size() -> None:
    text = "\n\n".join(
        [
            "عنوان قصير",
            " ".join(f"جملة رقم {i} توضح تفاصيل الإجراء المطلوب." for i in range(40)),
            "\n".join(f"- بند رقم {i}" for i in range(30)),
            "كلمةواحدةطويلةبلاحدود" * 40,
        ]
    )
    chunks = chunk_text(text, chunk_size=150, overlap=30)
    assert all(0 < len(c) <= 150 for c in chunks)
