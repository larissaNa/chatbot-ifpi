import re
import uuid
import logging

import fitz
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from .download_utils import baixar_pdf_resiliente
from apps.core.utils.fetcher import fetch_url_content

logger = logging.getLogger(__name__)

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l.strip() for l in text.split("\n")]
    cleaned = []
    for line in lines:
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
        else:
            line = re.sub(r"\s+", " ", line)
            cleaned.append(line)
    paragraphs = [l for l in cleaned if l]
    return "\n\n".join(paragraphs)


def _detect_language(text: str) -> str:
    if not text:
        return "desconhecido"
    lower = text.lower()
    markers = [
        " que ",
        " de ",
        " para ",
        " nao ",
        "cao",
        "coes",
        " nº ",
        " art. ",
    ]
    score = 0
    for marker in markers:
        if marker in lower:
            score += 1
    if score >= 2:
        return "pt"
    return "desconhecido"


def _extract_from_pdf_url(url: str):
    observacoes = []
    try:
        content = baixar_pdf_resiliente(url)
    except Exception as e:
        return "", 0, "PDF_TEXTUAL", [f"Erro ao baixar PDF resiliente: {e}"]
        
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception as e:
        return "", 0, "PDF_TEXTUAL", [f"Erro ao abrir PDF: {e}"]
    texts = []
    lengths = []
    for page in pdf:
        text = page.get_text("text") or ""
        texts.append(text)
        lengths.append(len(text.strip()))
    raw_text = "\n\n".join(texts)
    num_pages = len(pdf)
    pages_with_text = sum(1 for length in lengths if length >= 20)
    if num_pages == 0:
        tipo_extracao = "PDF_TEXTUAL"
        observacoes.append("PDF vazio ou sem paginas.")
    else:
        ratio = pages_with_text / float(num_pages)
        if ratio >= 0.5:
            tipo_extracao = "PDF_TEXTUAL"
        else:
            tipo_extracao = "PDF_OCR"
            observacoes.append("PDF provavelmente escaneado. OCR nao aplicado ou incompleto.")
    texto = _normalize_text(raw_text)
    
    # Validação obrigatória de conteúdo extraído
    if not texto or len(texto.strip()) < 100:
        logger.error(f"[EXTRACTOR] Falha na extração de texto do PDF {url}: Conteúdo insuficiente ({len(texto) if texto else 0} caracteres)")
        return "", 0, "PDF_TEXTUAL", ["Falha na extração de texto do PDF ou conteúdo insuficiente (< 100 caracteres)."]

    return texto, num_pages, tipo_extracao, observacoes


def _extract_from_html_url(url: str):
    observacoes = []
    # Usamos o novo fetcher robusto que suporta fallback e proxy
    try:
        html = fetch_url_content(url)
    except Exception as e:
        return None, "", 0, [f"Erro ao baixar HTML com fetcher robusto: {e}"]
        
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    titulo = None
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        if title_text:
            titulo = title_text
    parts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if text:
            parts.append(text)
    if not parts:
        body_text = soup.get_text(" ", strip=True)
        if body_text:
            parts.append(body_text)
    raw_text = "\n\n".join(parts)
    texto = _normalize_text(raw_text)
    if texto:
        paginas_estimadas = max(1, int(len(texto) / 1800))
    else:
        paginas_estimadas = 0
        observacoes.append("Nenhum conteudo textual significativo encontrado no HTML.")
    return titulo, texto, paginas_estimadas, observacoes


@tool
def extrair_conteudo(analise: dict):
    """
    Recebe a analise de um link e extrai o conteudo textual e metadados.
    Suporta PDF direto, HTML com links para PDF e HTML textual.
    Retorna um dicionario com os documentos extraidos e indicacao do proximo agente.
    """
    fonte = analise.get("url") or analise.get("fonte") or ""
    tipo_conteudo = analise.get("tipo_conteudo")
    pdfs = analise.get("pdfs_encontrados") or []
    documentos = []
    observacoes = []
    tipo_extracao_global = None
    if tipo_conteudo == "PDF_DIRETO":
        texto, paginas, tipo_extracao, obs = _extract_from_pdf_url(fonte)
        if obs:
            observacoes.extend(obs)
        idioma = _detect_language(texto)
        doc = {
            "id_documento": str(uuid.uuid4()),
            "titulo": analise.get("titulo"),
            "texto": texto,
            "metadata": {
                "paginas_estimadas": paginas,
                "idioma": idioma or "desconhecido",
                "tipo_extracao": tipo_extracao,
            },
        }
        documentos.append(doc)
        tipo_extracao_global = tipo_extracao
    elif tipo_conteudo == "HTML_COM_PDF":
        if not pdfs:
            observacoes.append("tipo_conteudo=HTML_COM_PDF mas pdfs_encontrados esta vazio.")
        for item in pdfs:
            pdf_url = item.get("url")
            if not pdf_url:
                continue
            texto, paginas, tipo_extracao, obs = _extract_from_pdf_url(pdf_url)
            if obs:
                observacoes.append(f"{pdf_url}: " + " ".join(obs))
            idioma = _detect_language(texto)
            doc = {
                "id_documento": str(uuid.uuid4()),
                "titulo": item.get("descricao") or analise.get("titulo"),
                "texto": texto,
                "metadata": {
                    "paginas_estimadas": paginas,
                    "idioma": idioma or "desconhecido",
                    "tipo_extracao": tipo_extracao,
                },
            }
            documentos.append(doc)
            if not tipo_extracao_global:
                tipo_extracao_global = tipo_extracao
            elif tipo_extracao_global == "PDF_TEXTUAL" and tipo_extracao == "PDF_OCR":
                tipo_extracao_global = "PDF_OCR"
        if not tipo_extracao_global:
            tipo_extracao_global = "PDF_TEXTUAL"
    elif tipo_conteudo == "HTML_TEXTO":
        titulo, texto, paginas, obs = _extract_from_html_url(fonte)
        if obs:
            observacoes.extend(obs)
        idioma = _detect_language(texto)
        doc = {
            "id_documento": str(uuid.uuid4()),
            "titulo": titulo or analise.get("titulo"),
            "texto": texto,
            "metadata": {
                "paginas_estimadas": paginas,
                "idioma": idioma or "desconhecido",
                "tipo_extracao": "HTML",
            },
        }
        documentos.append(doc)
        tipo_extracao_global = "HTML"
    else:
        observacoes.append(f"tipo_conteudo invalido ou nao suportado: {tipo_conteudo}")
        tipo_extracao_global = "HTML"
    return {
        "fonte": fonte,
        "tipo_extracao": tipo_extracao_global or "HTML",
        "documentos": documentos,
        "observacoes": " ".join(observacoes).strip(),
        "proximo_agente": "AGENTE_PROCESSAMENTO",
    }
