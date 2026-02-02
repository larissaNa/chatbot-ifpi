from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import os

def setup_vectorstore(persist_directory="chroma_db"):
    # Define o diretório de persistência na raiz do projeto (mesmo local usado pelos agentes)
    # apps/core/services/utils.py -> ../../../ -> root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
    persist_path = os.path.join(project_root, persist_directory)

    print(f"\n[DEBUG] --- CONFIGURAÇÃO CHROMA DB ---")
    print(f"[DEBUG] Base Dir (utils.py): {base_dir}")
    print(f"[DEBUG] Project Root calculado: {project_root}")
    print(f"[DEBUG] Diretório de persistência FINAL: {persist_path}")
    print(f"[DEBUG] ------------------------------\n")

    # Inicializa embeddings com o mesmo modelo usado no processing_agent
    # Garante compatibilidade semântica
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings = HuggingFaceEmbeddings(model_name=model_name)

    # Conecta ao ChromaDB existente (ou cria vazio se não existir)
    # Usa a mesma collection 'crencas_institucionais' usada pelo chromadb_agent
    vectorstore = Chroma(
        collection_name="crencas_institucionais",
        embedding_function=embeddings,
        persist_directory=persist_path
    )
    
    # NÃO carrega arquivos locais. A base deve ser populada apenas via fluxo de revisão de crenças.
    try:
        count = vectorstore._collection.count()
        print(f"[INFO] Conectado à base vetorial em '{persist_path}'. Documentos indexados: {count}")
    except Exception as e:
        print(f"[INFO] Conectado à base vetorial em '{persist_path}'. (Não foi possível contar documentos: {e})")

    return vectorstore
