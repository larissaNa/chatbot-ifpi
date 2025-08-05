from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

def setup_vectorstore(persist_directory="chatbot", pdf_paths=None):
    if pdf_paths is None:
        pdf_paths = [
            "apps/documentos/normativas.pdf",
            "apps/documentos/Lei-8812.pdf"
        ]

    # Verifica se a base já existe
    if os.path.exists(persist_directory) and os.listdir(persist_directory):
        print("✅ Base vetorial já existe. Carregando sem adicionar documentos.")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = Chroma(
            collection_name="baseDeDados",
            embedding_function=embeddings,
            persist_directory=persist_directory
        )
        return vectorstore

    # Caso contrário, criar nova base
    print("[INFO] Criando nova base vetorial...")
    all_documents = []

    for path in pdf_paths:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            print(f"[AVISO] Arquivo não encontrado: {abs_path}. Pulando.")
            continue

        print(f"[INFO] Carregando: {abs_path}")
        loader = PyPDFLoader(abs_path)
        pages = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        docs = text_splitter.split_documents(pages)
        print(f"[INFO] {len(docs)} trechos extraídos de {os.path.basename(path)}")

        all_documents.extend(docs)

    if not all_documents:
        raise ValueError("Nenhum documento válido foi carregado para a base vetorial.")

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma(
        collection_name="baseDeDados",
        embedding_function=embeddings,
        persist_directory=persist_directory
    )

    vectorstore.add_documents(all_documents)
    vectorstore.persist()
    print(f"[INFO] Base vetorial criada e persistida em '{persist_directory}'.")

    return vectorstore
