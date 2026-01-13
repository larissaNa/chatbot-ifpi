from langchain_core.tools import tool
from apps.authentication.models import DocumentoOficial
from apps import db
import requests
from bs4 import BeautifulSoup

@tool
def buscar_documentos_oficiais():
    """
    Busca todos os links (PDFs) cadastrados pelo administrador no banco de dados.
    Caso o link seja uma página, ele coleta todos os PDFs encontrados nela.
    Retorna uma lista de URLs válidas para download.
    """
    fontes = DocumentoOficial.query.filter_by(ativo=True).all()
    pdf_links = []

    for fonte in fontes:
        try:
            url = fonte.url.strip()
            if url.endswith(".pdf"):
                pdf_links.append(url)
            else:
                resp = requests.get(url, timeout=10)
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.lower().endswith(".pdf"):
                        # Corrige links relativos
                        if href.startswith("http"):
                            pdf_links.append(href)
                        else:
                            pdf_links.append(requests.compat.urljoin(url, href))
        except Exception as e:
            print(f"[Erro ao buscar PDFs em] {fonte.url} → {e}")

    return list(set(pdf_links))
