from vertexai import init as vertex_init
from langchain_google_vertexai import ChatVertexAI

def get_llm():
    # Inicializa o Vertex AI com o projeto e localização corretos
    vertex_init(
        project="gen-lang-client-0261212364",  # substitua pelo ID real do seu projeto
        location="us-central1"                 # ou a região habilitada
    )
    
    # Inicializa o modelo Gemini 2.5 Flash com LangChain
    llm = ChatVertexAI(
        model="gemini-2.5-flash",  # nome exato do modelo
        temperature=0.0
    )

    return llm
