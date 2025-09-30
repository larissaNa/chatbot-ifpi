from langchain_chroma import Chroma
from apps.core.llm_config import HuggingFaceEmbeddings

def get_vectorstore():
    embeddings = HuggingFaceEmbeddings()
    vectorstore = Chroma(
        collection_name="baseDeDados",
        embedding_function=embeddings,
        persist_directory="./chatbot"
    )
    return vectorstore