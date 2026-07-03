"""Construye/reconstruye el índice vectorial del RAG."""
from app.rag.retriever import build_index

if __name__ == "__main__":
    n = build_index()
    print(f"Índice RAG construido: {n} chunks.")
