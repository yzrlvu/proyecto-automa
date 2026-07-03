"""Pipeline RAG: indexa la base de conocimiento de la clínica en Chroma y expone
una tool de recuperación para los agentes.

- Documentos: data/knowledge_base/*.md (políticas, FAQ)
- Chunking: RecursiveCharacterTextSplitter (500 chars, overlap 80)
- Embeddings: sentence-transformers/all-MiniLM-L6-v2 (local, sin costo por token)
- Vector store: Chroma persistente
"""
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

_vectorstore: Chroma | None = None
KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"


def _get_embeddings():
    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model)


def build_index() -> int:
    """(Re)construye el índice vectorial a partir de la base de conocimiento."""
    loader = DirectoryLoader(str(KB_DIR), glob="*.md", loader_cls=TextLoader,
                             loader_kwargs={"encoding": "utf-8"})
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    chunks = splitter.split_documents(docs)
    global _vectorstore
    _vectorstore = Chroma.from_documents(
        chunks, _get_embeddings(),
        persist_directory=get_settings().chroma_persist_dir,
        collection_name="clinica_kb",
    )
    return len(chunks)


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            persist_directory=get_settings().chroma_persist_dir,
            collection_name="clinica_kb",
            embedding_function=_get_embeddings(),
        )
    return _vectorstore


@tool
def consultar_politicas_clinica(pregunta: str) -> str:
    """Busca en la base de conocimiento de la clínica (políticas, horarios, tarifas,
    seguros, FAQ) la información relevante para responder una pregunta del paciente."""
    docs = get_vectorstore().similarity_search(pregunta, k=get_settings().rag_top_k)
    if not docs:
        return "No se encontró información relevante en la base de conocimiento."
    return "\n---\n".join(d.page_content for d in docs)
