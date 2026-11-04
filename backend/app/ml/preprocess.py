"""NLP preprocessing pipeline (SRS FR-04).

Steps: lowercase -> strip markup -> remove punctuation -> tokenize ->
stop-word removal -> light suffix normalization -> whitespace collapse.
"""

import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "done", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "s", "same", "she", "should", "so", "some", "such",
    "t", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with",
    "within", "you", "your", "yours", "yourself", "yourselves", "also",
    "please", "near", "very", "much", "many", "some", "one", "two", "want",
    "need", "needs", "need", "want", "wants", "went", "going",
}

_TAG_RE = re.compile(r"<[^>]+>")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def clean_text(text: str) -> str:
    """Lowercase, strip markup/punctuation, normalize whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def normalize_token(token: str) -> str:
    """Very light stemming: common English suffixes only.

    Order matters: plural 's' is checked last and never strips from
    words ending in 'ss' (e.g. 'bus', 'cross').
    """
    if len(token) <= 3:
        return token
    for suffix in ("ing", "edly", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith("ss") and len(token) >= 4:
        return token[:-1]
    return token


def process(text: str) -> str:
    """Full pipeline: returns the normalized token string."""
    tokens = []
    for tok in tokenize(clean_text(text)):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        tok = normalize_token(tok)
        if tok and tok not in STOPWORDS:
            tokens.append(tok)
    return " ".join(tokens)


def problem_text(title: str, description: str) -> str:
    return process(f"{title}. {description}")


def doc_text(title: str, description: str, semantic: bool = False) -> str:
    """Text representation for embedding.

    TF-IDF: full NLP pipeline (stop-words, suffix normalization).
    Sentence transformers: light cleaning only - stemming and stop-word
    removal hurt semantic embedding quality.
    """
    raw = f"{title}. {description}"
    return clean_text(raw) if semantic else process(raw)
