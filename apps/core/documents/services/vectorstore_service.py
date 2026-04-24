import os


def setup_vectorstore(persist_directory: str = "chroma_db"):
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", "..", ".."))
    persist_path = os.path.join(project_root, persist_directory)

    model_name = os.getenv(
        "EMBEDDINGS_MODEL_NAME",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
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
