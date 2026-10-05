from app.tools.rag_retriever import RAGRetriever


def test_rag_finds_salt_advice():
    docs = RAGRetriever().search("Сколько соли можно при гипертонии?")
    assert docs and "соль" in docs[0].lower()


def test_rag_returns_nothing_for_unrelated_query():
    assert RAGRetriever().search("рецепт шарлотки с яблоками") == []
