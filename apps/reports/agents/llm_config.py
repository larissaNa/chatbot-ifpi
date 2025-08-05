from langchain.chat_models import init_chat_model

def get_llm():
    return init_chat_model("anthropic:claude-3-5-sonnet-latest")
