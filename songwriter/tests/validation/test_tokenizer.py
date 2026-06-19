from songwriter.api.validation.tokenizer import tokenize_line


def test_tokenize_drops_punctuation_and_lowercases(conn):
    toks = tokenize_line("You called me late!", conn)
    assert [t.word for t in toks] == ["you", "called", "me", "late"]


def test_tokenize_attaches_phonetic_data(conn):
    toks = tokenize_line("love above", conn)
    assert toks[0].word == "love"
    assert toks[0].rhyme_class == "AH-V"
    assert toks[1].rhyme_class == "AH-V"
    assert toks[0].syllables == 1


def test_tokenize_marks_unknown_words(conn):
    toks = tokenize_line("schmlorp love", conn)
    assert toks[0].unknown is True
    assert toks[0].syllables == 0
    assert toks[1].unknown is False


def test_tokenize_empty_line(conn):
    assert tokenize_line("", conn) == []
