"""Легкий RAG без внешних зависимостей и скачивания моделей.

Берет утвержденные .txt материалы из каталога knowledge/ (settings.rag_docs_dir), режет их на абзацы
и ищет релевантные по пересечению нормализованных слов (TF-IDF, "стемминг" по префиксу слова).
Агент отвечает только тем, что нашлось в материалах; если ничего не найдено - не выдумывает.

Проверка:  python -m app.tools.rag_retriever --query "сколько соли можно"
"""
import argparse
import math
import re
from collections import Counter
from pathlib import Path

from app.core.config import settings

_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_STOP = {"и", "в", "на", "не", "что", "как", "я", "мне", "можно", "это", "по", "с", "а", "но", "или", "ли", "для"}
MIN_SCORE = 0.3


def _stem(word: str) -> str:
    """Грубый стемминг по префиксу: 'соль'/'соли' -> 'сол', 'давление'/'давления' -> 'давле'."""
    return word[: min(5, max(3, len(word) - 1))]


def _tokens(text: str) -> list[str]:
    words = (w.lower().replace("ё", "е") for w in _WORD_RE.findall(text))
    return [_stem(w) for w in words if len(w) > 2 and w not in _STOP]


class RAGRetriever:
    def __init__(self, docs_dir: str | None = None):
        self.docs_dir = Path(docs_dir or settings.rag_docs_dir)
        self.chunks: list[tuple[str, str, Counter]] = []  # (источник, текст, счетчик токенов)
        self._idf: dict[str, float] = {}
        self.index()

    def index(self) -> int:
        self.chunks = []
        if self.docs_dir.is_dir():
            for path in sorted(self.docs_dir.glob("**/*.txt")):
                text = path.read_text(encoding="utf-8", errors="ignore")
                for part in re.split(r"\n\s*\n", text):
                    part = part.strip()
                    tokens = _tokens(part)
                    if len(tokens) >= 4:
                        self.chunks.append((path.name, part, Counter(tokens)))
        df: Counter = Counter()
        for _, _, counter in self.chunks:
            df.update(counter.keys())
        total = max(len(self.chunks), 1)
        self._idf = {tok: math.log(1 + total / count) for tok, count in df.items()}
        return len(self.chunks)

    def search(self, query: str, k: int = 3) -> list[str]:
        query_tokens = set(_tokens(query))
        if not query_tokens or not self.chunks:
            return []
        scored = []
        for _, text, counter in self.chunks:
            hits = [t for t in query_tokens if t in counter]
            if not hits:
                continue
            score = sum(self._idf.get(t, 0.0) for t in hits) / sum(self._idf.get(t, 1.0) for t in query_tokens)
            scored.append((score, text))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for score, text in scored[:k] if score >= MIN_SCORE]


retriever = RAGRetriever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="")
    args = parser.parse_args()
    print(f"Проиндексировано абзацев: {len(retriever.chunks)}")
    for found in retriever.search(args.query):
        print("-", found)
