import os
from pathlib import Path

from vertexai import init as vertex_init
from langchain_google_vertexai import ChatVertexAI


def _ensure_google_application_credentials():
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    local_credentials_path = (Path(__file__).resolve().parents[1] / "credenciais.json")
    if local_credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(local_credentials_path)


def get_llm():
    _ensure_google_application_credentials()

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEXAI_PROJECT") or "gen-lang-client-0261212364"
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEXAI_LOCATION") or "us-central1"

    vertex_init(project=project, location=location)

    return ChatVertexAI(model="gemini-2.5-flash", temperature=0.0)
