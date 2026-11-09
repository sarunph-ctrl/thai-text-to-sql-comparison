"""Step 1 of the pipeline: turn raw user text into a clean, tokenized form.

Rules applied, in order:
  1. Strip zero-width / invisible characters that sneak in from copy-paste.
  2. Convert Thai numerals (๑๒๓) to arabic digits.
  3. Collapse repeated characters used for emphasis ("มากกกก" -> "มาก").
  4. Lowercase (affects only Latin runs; Thai has no case).
  5. Tokenize with PyThaiNLP's newmm engine, seeded with our domain dictionary
     so multi-word terms like "ยอดขาย" or "เดือนที่แล้ว" stay as one semantic
     unit instead of being split.
  6. Drop politeness / filler stopwords from the lexicon.

Returns both the cleaned string (for regex-based time parsing, which wants
substrings) and the token list (for the intent matcher).
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass

from pythainlp.tokenize import word_tokenize
from pythainlp.corpus import thai_words
from pythainlp.util import Trie

from app.config_loader import load_lexicon, load_time_words

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_REPEAT = re.compile(r"(.)\1{3,}")  # 4+ repeats of any char (emphasis, e.g. "มากกกกก")
# NOTE: threshold is 4, not 3 - legitimate Thai words can have 3 identical
# vowels in a row at a word boundary (e.g. "ต่อ" + "ออเดอร์" -> "ต่อออเดอร์"
# has "อออ"), and collapsing those mangled real words during testing.


def _build_custom_dict() -> set[str]:
    """Collect multi-char domain terms so the tokenizer doesn't split them."""
    lex = load_lexicon()
    tw = load_time_words()
    words: set[str] = set()
    for ent in lex["entities"].values():
        words.update(ent["synonyms"])
    for m in lex["metrics"].values():
        words.update(m["synonyms"])
    for group in (lex["status_values"], lex["payment_methods"], lex["comparators"]):
        for syns in group.values():
            words.update(syns)
    for phrase_map in (tw["relative_points"], tw["relative_periods"]):
        words.update(phrase_map.keys())
    for names in tw["months"].values():
        words.update(names)
    return {w for w in words if len(w) > 1}


_CUSTOM_DICT = Trie(set(thai_words()) | _build_custom_dict())
_STOPWORDS = set(load_lexicon()["stopwords"])
_THAI_DIGITS = load_time_words()["thai_digits"]


def _thai_digits_to_arabic(text: str) -> str:
    for th, ar in _THAI_DIGITS.items():
        text = text.replace(th, ar)
    return text


@dataclass
class Normalized:
    raw: str
    clean_text: str       # cleaned, still human-readable (for regex time parsing)
    tokens: list[str]     # tokenized, stopwords removed (for intent matching)


def normalize(raw: str) -> Normalized:
    text = unicodedata.normalize("NFC", raw)
    text = _ZERO_WIDTH.sub("", text)
    text = _thai_digits_to_arabic(text)
    text = _REPEAT.sub(r"\1", text)
    text = text.strip()

    tokens = word_tokenize(text, custom_dict=_CUSTOM_DICT, engine="newmm", keep_whitespace=False)

    tokens = [t for t in tokens if t.strip() and t not in _STOPWORDS]
    return Normalized(raw=raw, clean_text=text, tokens=tokens)
