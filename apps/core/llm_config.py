from langchain.chat_models import init_chat_model
from langchain_huggingface import HuggingFaceEmbeddings

def get_llm():
    return init_chat_model("anthropic:claude-3-5-sonnet-latest")


def embeddings_hf():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")