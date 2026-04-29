import os
from pathlib import Path

def _ensure_google_application_credentials():
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    local_credentials_path = (Path(__file__).resolve().parents[1] / "credenciais.json")
    if local_credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(local_credentials_path)

def get_llm():
    # Preferência para Google Generative AI (Gemini API) se a chave estiver presente
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_api_key, temperature=0.0)

    # Fallback para Vertex AI
    from vertexai import init as vertex_init
    from langchain_google_vertexai import ChatVertexAI

    _ensure_google_application_credentials()

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEXAI_PROJECT") or "gen-lang-client-0261212364"
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEXAI_LOCATION") or "us-central1"

    vertex_init(project=project, location=location)

    return ChatVertexAI(model="gemini-1.5-flash", temperature=0.0)
