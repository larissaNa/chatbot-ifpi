from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def setup_vectorstore(persist_directory="chatbot", pdf_path="documentos/normativas.pdf"):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma(
        collection_name="baseDeDados",
        embedding_function=embeddings,
        persist_directory=persist_directory
    )

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    docs = text_splitter.split_documents(pages)

    vectorstore.add_documents(docs)

    return vectorstore
