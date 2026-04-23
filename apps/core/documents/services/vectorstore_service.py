import os

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


def setup_vectorstore(persist_directory="chroma_db"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", "..", ".."))
    persist_path = os.path.join(project_root, persist_directory)

    print("\n[DEBUG] --- CONFIGURAÇÃO CHROMA DB ---")
    print(f"[DEBUG] Base Dir (vectorstore_service.py): {base_dir}")
    print(f"[DEBUG] Project Root calculado: {project_root}")
    print(f"[DEBUG] Diretório de persistência FINAL: {persist_path}")
    print("[DEBUG] ------------------------------\n")

    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings = HuggingFaceEmbeddings(model_name=model_name)

    vectorstore = Chroma(
        collection_name="crencas_institucionais",
        embedding_function=embeddings,
        persist_directory=persist_path,
    )

    try:
        count = vectorstore._collection.count()
        print(f"[INFO] Conectado à base vetorial em '{persist_path}'. Documentos indexados: {count}")
    except Exception as e:
        print(f"[INFO] Conectado à base vetorial em '{persist_path}'. (Não foi possível contar documentos: {e})")

    return vectorstore
