from vertexai import init as vertex_init
from langchain.chat_models import init_chat_model

def get_llm():
    # Inicializa o Vertex AI com o projeto e localização corretos
    vertex_init(
        project="gen-lang-client-0261212364",  # substitua pelo ID real do projeto
        location="us-central1"     # ou a região onde o modelo está habilitado
    )
    
    return init_chat_model("google_vertexai:gemini-2.5-flash", temperature=0)
