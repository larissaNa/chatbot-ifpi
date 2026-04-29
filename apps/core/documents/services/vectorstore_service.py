import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

_vectorstore = None

def setup_vectorstore():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Caminho para a raiz do projeto: apps/core/documents/services -> 4 níveis acima
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", "..", ".."))
    persist_path = os.path.join(project_root, "chroma_db")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    vectorstore = Chroma(
        collection_name="crencas_institucionais",
        embedding_function=embeddings,
        persist_directory=persist_path
    )

    try:
        count = vectorstore._collection.count()
        print(f"[INFO] Vectorstore carregado. Documentos indexados: {count}")
    except Exception as e:
        print(f"[INFO] Vectorstore carregado. (Não foi possível contar documentos: {e})")

    return vectorstore

def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = setup_vectorstore()
    return _vectorstore
