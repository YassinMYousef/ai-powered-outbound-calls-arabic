from app.conversation.rag.lexical import rank, tokenize


def test_tokenize_strips_diacritics_and_tatweel() -> None:
    assert tokenize("العُمَلاءُ") == tokenize("العملاء") == ["العملاء"]
    assert tokenize("مـــرحبا") == ["مرحبا"]


def test_tokenize_unifies_orthographic_variants() -> None:
    # alef hamza forms, final yaa/alef maqsura, and taa marbuta all collapse
    # so query spellings match document spellings.
    assert tokenize("أحمد") == tokenize("احمد")
    assert tokenize("إلى") == tokenize("الى")
    assert tokenize("مكتبة") == tokenize("مكتبه")


def test_tokenize_splits_mixed_arabic_latin() -> None:
    assert tokenize("رمز الخطأ E-450") == ["رمز", "الخطا", "e", "450"]


def test_rank_prefers_document_with_more_query_terms() -> None:
    texts = [
        "إجراءات تحديث بيانات العميل في النظام",
        "تحديث كلمة المرور",
        "قائمة الإجازات السنوية",
    ]
    ranked = rank("تحديث بيانات العميل", texts, top_n=3)
    assert [index for index, _ in ranked] == [0, 1]  # doc 2 shares nothing → absent
    assert ranked[0][1] > ranked[1][1]


def test_rank_matches_across_spelling_variants() -> None:
    # Query with hamza/diacritics still hits the plainly-spelled document.
    ranked = rank("بياناتُ العميلِ", ["تحديث بيانات العميل"], top_n=1)
    assert ranked == [(0, ranked[0][1])]
    assert ranked[0][1] > 0


def test_rank_returns_empty_when_nothing_matches() -> None:
    assert rank("سؤال غريب", ["نص لا علاقة له إطلاقا"], top_n=5) == []
    assert rank("سؤال", [], top_n=5) == []
    assert rank("", ["نص"], top_n=5) == []


def test_rank_rare_term_outweighs_common_term() -> None:
    # "النظام" appears everywhere (low idf); "الفوترة" in one doc (high idf).
    texts = [
        "النظام يشرح الفوترة",
        "النظام يشرح الصلاحيات في النظام",
        "النظام يشرح التقارير في النظام",
    ]
    ranked = rank("الفوترة في النظام", texts, top_n=3)
    assert ranked[0][0] == 0
