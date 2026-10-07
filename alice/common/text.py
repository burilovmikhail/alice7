"""Text utilities: crude ru/en stemming, FTS queries, name matching, token estimates."""

import re
from datetime import date

WORD_RE = re.compile(r"\w+", re.U)

STOPWORDS = {
    # ru
    "это", "как", "что", "где", "когда", "кто", "чем", "так", "там", "тут", "ещё", "еще",
    "уже", "или", "для", "про", "при", "над", "под", "без", "его", "её", "она", "они",
    "оно", "мне", "меня", "мой", "моя", "моё", "мои", "тебя", "тебе", "твой", "был",
    "была", "было", "были", "есть", "быть", "вот", "все", "всё", "помнишь", "скажи",
    "расскажи", "знаешь", "мы", "нас", "наш", "очень", "просто",
    # en
    "the", "and", "you", "your", "are", "was", "were", "what", "where", "when", "who", "how",
    "that", "this", "with", "for", "about", "did", "does", "have", "has", "had", "not", "but",
    "can", "could", "would", "should", "just", "really", "remember", "tell", "know", "me", "my",
    "our", "we", "from", "there", "they", "them", "then", "than", "any", "some", "is", "it",
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def today_human(d: date) -> str:
    return f"{d.isoformat()}, {WEEKDAYS[d.weekday()]}"


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def stem(word: str) -> str:
    """Cut the ending: «Маши» -> «маш», "sisters" -> "siste". Crude but dependency-free; used as a prefix."""
    word = word.lower()
    return word[: max(3, len(word) - 2)]


def fts_query(text: str) -> str | None:
    terms = {stem(w) for w in words(text) if len(w) >= 3 and w not in STOPWORDS}
    if not terms:
        return None
    return " OR ".join(f'"{t}"*' for t in sorted(terms))


def name_matches(name: str, text_words: list[str]) -> bool:
    """Every word of the name occurs in the text, up to the ending."""
    parts = words(name)
    return bool(parts) and all(any(w.startswith(stem(p)) for w in text_words) for p in parts)


def content_stems(text: str) -> set[str]:
    return {stem(w) for w in words(text) if len(w) >= 3 and w not in STOPWORDS}


def stem_overlap(needle: str, haystack: str, ignore: set[str] = frozenset()) -> float:
    """Share of the needle's content stems found in the haystack (for matching gold memories).
    `ignore` drops uninformative stems (e.g. the user's name, present in most memories)."""
    need = content_stems(needle)
    need = need - ignore or need
    if not need:
        return 0.0
    hay = words(haystack)
    return sum(any(w.startswith(s) for w in hay) for s in need) / len(need)


def estimate_tokens(text: str) -> int:
    # ~3 chars per token for Russian, ~4 for English; precision doesn't matter here
    return len(text) // 3 + 1


def short(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"
