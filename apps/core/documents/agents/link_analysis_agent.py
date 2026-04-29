from datetime import datetime
from urllib.parse import urlparse
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from apps import db
from apps.authentication import DocumentoOficial


# =========================
# 🔐 SESSION ROBUSTA
# =========================
def _get_robust_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    })

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# =========================
# 🌐 PROXY (OPCIONAL)
# =========================
def _get_proxies():
    http = os.getenv("PROXY_HTTP")
    https = os.getenv("PROXY_HTTPS")

    if http and https:
        return {
            "http": http,
            "https": https
        }
    return None


# =========================
# 🔁 REQUEST COM FALLBACK
# =========================
def _make_request(session, url):
    try:
        resp = session.get(
            url,
            stream=True,
            timeout=15,
            allow_redirects=True
        )

        # 🔥 fallback se 403
        if resp.status_code == 403:
            proxies = _get_proxies()

            if proxies:
                print("[INFO] 403 detectado → tentando com proxy...")
                resp = session.get(
                    url,
                    stream=True,
                    timeout=20,
                    allow_redirects=True,
                    proxies=proxies
                )

        return resp

    except Exception as e:
        raise e


# =========================
# 📄 BUSCAR PDFs
# =========================
@tool
def buscar_documentos_oficiais():
    """
    usca todos os links (PDFs) cadastrados pelo administrador no banco de dados. 
    Caso o link seja uma página, coleta todos os PDFs encontrados nela. 
    Retorna uma lista de URLs válidas para download.
    """
    fontes = DocumentoOficial.query.filter_by(ativo=True).all()
    pdf_links = []

    session = _get_robust_session()

    for fonte in fontes:
        try:
            url = fonte.url.strip()

            if url.endswith(".pdf"):
                pdf_links.append(url)
                continue

            resp = _make_request(session, url)

            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]

                if href.lower().endswith(".pdf"):
                    if href.startswith("http"):
                        pdf_links.append(href)
                    else:
                        pdf_links.append(requests.compat.urljoin(url, href))

        except Exception as e:
            print(f"[Erro ao buscar PDFs em] {fonte.url} -> {e}")

    return list(set(pdf_links))


# =========================
# 🔍 ANALISADOR PRINCIPAL
# =========================
def _analise_basica_url(url: str) -> dict:
    url = (url or "").strip()

    resultado = {
        "url": url,
        "status": "sucesso",
        "tipo_conteudo": "INVALIDO",
        "titulo": None,
        "mime_type": None,
        "pdfs_encontrados": [],
        "observacoes": "",
        "proximo_agente": "NENHUM",
    }

    # validação básica
    if not url:
        resultado["status"] = "erro"
        resultado["observacoes"] = "URL vazia."
        return resultado

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        resultado["status"] = "erro"
        resultado["observacoes"] = "URL inválida."
        return resultado

    session = _get_robust_session()

    # 🔁 request com fallback
    try:
        resp = _make_request(session, url)
        status_code = resp.status_code
    except Exception as e:
        resultado["status"] = "erro"
        resultado["observacoes"] = f"Erro ao acessar URL: {e}"
        return resultado

    # MIME
    mime_type = resp.headers.get("Content-Type")
    if mime_type:
        mime_type = mime_type.split(";")[0].strip()

    resultado["mime_type"] = mime_type

    # atualizar banco
    try:
        from flask import has_app_context

        if has_app_context():
            doc = DocumentoOficial.query.filter_by(url=url).first()
            if doc:
                doc.ultima_verificacao = datetime.utcnow()
                doc.ultimo_status_http = status_code
                db.session.commit()
    except:
        db.session.rollback()

    # erro final
    if status_code != 200:
        resultado["status"] = "erro"
        resultado["observacoes"] = f"Bloqueado (HTTP {status_code}) mesmo após fallback."
        return resultado

    # PDF direto
    if (mime_type and "pdf" in mime_type.lower()) or parsed.path.lower().endswith(".pdf"):
        resultado["tipo_conteudo"] = "PDF_DIRETO"
        resultado["proximo_agente"] = "AGENTE_EXTRACAO"
        resultado["observacoes"] = "PDF acessado com sucesso."
        return resultado

    # conteúdo inválido
    if mime_type and "html" not in mime_type.lower():
        resultado["status"] = "erro"
        resultado["observacoes"] = f"Tipo não suportado: {mime_type}"
        return resultado

    # HTML
    try:
        html = resp.text
    except Exception as e:
        resultado["status"] = "erro"
        resultado["observacoes"] = f"Erro ao ler HTML: {e}"
        return resultado

    soup = BeautifulSoup(html, "html.parser")

    titulo_tag = soup.find("title")
    if titulo_tag:
        resultado["titulo"] = titulo_tag.text.strip()

    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]

        if href.lower().endswith(".pdf"):
            pdf_url = href if href.startswith("http") else requests.compat.urljoin(url, href)
            pdfs.append({"url": pdf_url})

    resultado["pdfs_encontrados"] = pdfs

    if pdfs:
        resultado["tipo_conteudo"] = "HTML_COM_PDF"
        resultado["proximo_agente"] = "AGENTE_EXTRACAO"
        resultado["observacoes"] = f"{len(pdfs)} PDFs encontrados."
    else:
        resultado["tipo_conteudo"] = "HTML_TEXTO"
        resultado["proximo_agente"] = "AGENTE_EXTRACAO"
        resultado["observacoes"] = "Página HTML analisada."

    return resultado


# =========================
# 🧠 TOOL FINAL
# =========================
@tool
def analisar_link(url: str):
    """
    Analisa um link institucional e retorna metadados sobre o conteúdo,
    incluindo tipo (PDF, HTML), status de acesso e possíveis documentos encontrados.
    """
    return _analise_basica_url(url)