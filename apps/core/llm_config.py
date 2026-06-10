import os
from pathlib import Path


class BillingError(Exception):
    """Saldo da API esgotado ou conta bloqueada."""


def _raise_if_billing(exc: Exception) -> None:
    """Lança BillingError se a exceção indicar problema de cobrança."""
    msg = str(exc).lower()
    if any(k in msg for k in ("prepayment credits", "billing", "quota exceeded", "429")):
        raise BillingError(str(exc)) from exc


def _ensure_google_application_credentials():
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    local_credentials_path = (Path(__file__).resolve().parents[1] / "credenciais.json")
    if local_credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(local_credentials_path)


def get_llm():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            google_api_key=gemini_api_key,
            temperature=0.0,
            request_timeout=30,
            max_retries=0,  # sem retry — erros 429/404 não melhoram com espera
        )

    from vertexai import init as vertex_init
    from langchain_google_vertexai import ChatVertexAI

    _ensure_google_application_credentials()

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEXAI_PROJECT") or "gen-lang-client-0261212364"
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEXAI_LOCATION") or "us-central1"

    vertex_init(project=project, location=location)

    return ChatVertexAI(
        model="gemini-2.0-flash-lite",
        temperature=0.0,
        request_timeout=30,
        max_retries=0,
    )
