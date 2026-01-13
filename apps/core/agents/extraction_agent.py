from langchain_core.tools import tool
import requests
import fitz  # PyMuPDF

@tool
def extrair_texto_pdf(url: str) -> str:
    """
    Faz o download de um arquivo PDF a partir de uma URL
    e retorna todo o texto extraído do documento.
    """
    try:
        content = requests.get(url, timeout=15).content
        pdf = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in pdf)
        return text
    except Exception as e:
        return f"Erro ao extrair texto: {e}"
