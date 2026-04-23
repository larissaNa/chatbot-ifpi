from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from apps import db
from apps.authentication import DocumentoOficial


@tool
def buscar_documentos_oficiais():
    """
    Busca todos os links (PDFs) cadastrados pelo administrador no banco de dados.
    Caso o link seja uma página, coleta todos os PDFs encontrados nela.
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
                        if href.startswith("http"):
                            pdf_links.append(href)
                        else:
                            pdf_links.append(requests.compat.urljoin(url, href))
        except Exception as e:
            print(f"[Erro ao buscar PDFs em] {fonte.url} -> {e}")

    return list(set(pdf_links))


def _analise_basica_url(url: str) -> dict:
    url = (url or "").strip()

    resultado = {
        "url": url,
        "status": "ERRO",
        "tipo_conteudo": "INVALIDO",
        "titulo": None,
        "mime_type": None,
        "pdfs_encontrados": [],
        "observacoes": "",
        "proximo_agente": "NENHUM",
    }

    if not url:
        resultado["observacoes"] = "URL vazia."
        return resultado

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        resultado["observacoes"] = "URL invalida."
        return resultado

    try:
        head_resp = requests.head(url, allow_redirects=True, timeout=10)
        status_code = head_resp.status_code
    except Exception as e:
        resultado["observacoes"] = f"Erro ao acessar URL (HEAD): {e}"
        return resultado

    mime_type = head_resp.headers.get("Content-Type")
    if mime_type:
        mime_type = mime_type.split(";")[0].strip()
    resultado["mime_type"] = mime_type

    try:
        try:
            from flask import has_app_context

            in_app_context = bool(has_app_context())
        except Exception:
            in_app_context = False

        if in_app_context:
            doc = DocumentoOficial.query.filter_by(url=url).first()
            if doc:
                doc.ultima_verificacao = datetime.utcnow()
                doc.ultimo_status_http = status_code
                db.session.commit()
    except Exception as e:
        print(f"[analisar_link] erro ao atualizar DocumentoOficial: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass

    if status_code != 200:
        resultado["observacoes"] = f"URL inacessivel (status HTTP {status_code})."
        return resultado

    resultado["status"] = "SUCESSO"

    if (mime_type and mime_type.lower() == "application/pdf") or parsed.path.lower().endswith(".pdf"):
        resultado["tipo_conteudo"] = "PDF_DIRETO"
        resultado["proximo_agente"] = "AGENTE_EXTRACAO"

        url_lower = url.lower()
        palavras = []
        candidatos = [
            "ifpi",
            "instituto federal do piauí",
            "resolucao",
            "resolucao",
            "portaria",
            "norma",
            "edital",
        ]
        for k in candidatos:
            if k in url_lower:
                palavras.append(k)

        if palavras:
            resultado["observacoes"] = "Indicios de documento oficial na URL: " + ", ".join(sorted(set(palavras)))
        else:
            resultado["observacoes"] = "Link PDF direto; analise de conteudo delegada ao proximo agente."

        return resultado

    if mime_type and "html" not in mime_type.lower():
        resultado["status"] = "ERRO"
        resultado["tipo_conteudo"] = "INVALIDO"
        resultado["observacoes"] = f"Tipo de conteudo nao suportado: {mime_type}."
        resultado["proximo_agente"] = "NENHUM"
        return resultado

    try:
        resp = requests.get(url, timeout=15)
    except Exception as e:
        resultado["status"] = "ERRO"
        resultado["tipo_conteudo"] = "INVALIDO"
        resultado["observacoes"] = f"Erro ao carregar HTML: {e}"
        return resultado

    if resp.status_code != 200:
        resultado["status"] = "ERRO"
        resultado["tipo_conteudo"] = "INVALIDO"
        resultado["observacoes"] = f"URL inacessivel na requisicao GET (status HTTP {resp.status_code})."
        return resultado

    html = resp.text or ""
    soup = BeautifulSoup(html, "html.parser")

    titulo_tag = soup.find("title")
    if titulo_tag and titulo_tag.text.strip():
        resultado["titulo"] = titulo_tag.text.strip()

    pdfs_encontrados = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().endswith(".pdf"):
            pdf_url = href if href.startswith("http") else requests.compat.urljoin(url, href)
            descricao = (a.get_text() or "").strip() or ""
            pdfs_encontrados.append({"url": pdf_url, "descricao": descricao})

    resultado["pdfs_encontrados"] = pdfs_encontrados

    texto_base = (resultado["titulo"] or "") + " " + soup.get_text(separator=" ", strip=True)[:5000]
    texto_lower = texto_base.lower()
    palavras_chave = []
    candidatos_texto = [
        "ifpi",
        "instituto federal do piauí",
        "resolucao",
        "resolucao",
        "portaria",
        "norma",
        "instrucao normativa",
        "instrucao normativa",
        "edital",
        "comunicado",
    ]
    for k in candidatos_texto:
        if k in texto_lower:
            palavras_chave.append(k)

    partes_obs = []
    if pdfs_encontrados:
        partes_obs.append(f"{len(pdfs_encontrados)} PDF(s) encontrado(s) na pagina.")
    if palavras_chave:
        partes_obs.append("Indicios de documento oficial: " + ", ".join(sorted(set(palavras_chave))))
    if not partes_obs:
        partes_obs.append("Pagina HTML analisada sem indicios fortes de documento oficial.")

    resultado["observacoes"] = " ".join(partes_obs)

    if pdfs_encontrados:
        resultado["tipo_conteudo"] = "HTML_COM_PDF"
        resultado["proximo_agente"] = "AGENTE_EXTRACAO"
    else:
        tamanho_texto = len(soup.get_text(strip=True))
        if tamanho_texto >= 50:
            resultado["tipo_conteudo"] = "HTML_TEXTO"
            resultado["proximo_agente"] = "AGENTE_EXTRACAO"
        else:
            resultado["tipo_conteudo"] = "INVALIDO"
            resultado["proximo_agente"] = "NENHUM"
            resultado["observacoes"] += " Conteudo textual insuficiente (< 50 caracteres)."

    return resultado


@tool
def analisar_link(url: str):
    """
    Analisa um link institucional cadastrado, valida a URL e classifica
    o tipo de conteudo, retornando um dicionario JSON-ready com metadados
    e a indicacao do proximo agente da pipeline.
    """
    return _analise_basica_url(url)
