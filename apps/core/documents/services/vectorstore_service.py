import os

_vectorstore = None

def setup_vectorstore():
    from langchain_chroma import Chroma

    ENV = os.getenv("ENV", "dev")

    if ENV == "prod":
        # 🔵 PRODUÇÃO - leve (Render)
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001"
        )

        vectorstore = Chroma(
            collection_name="crencas_institucionais",
            embedding_function=embeddings
        )

    else:
        # 🟢 DESENVOLVIMENTO - local
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            # Fallback caso a lib não esteja instalada mesmo em dev
            print("[ERRO] langchain_huggingface não encontrada. Use 'pip install langchain-huggingface' para dev.")
            raise

        base_dir = os.path.dirname(os.path.abspath(__file__))
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
        print(f"[INFO] Ambiente: {ENV}. Documentos indexados: {count}")
    except Exception as e:
        print(f"[INFO] Ambiente: {ENV}. (Não foi possível contar documentos: {e})")

    return vectorstore

def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = setup_vectorstore()
    return _vectorstore
