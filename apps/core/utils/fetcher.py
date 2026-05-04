import os
import requests
import logging
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

def get_proxies():
    """
    Lê os proxies das variáveis de ambiente.
    """
    http = os.getenv("PROXY_HTTP")
    https = os.getenv("PROXY_HTTPS")
    return {
        "http": http,
        "https": https,
    }

def get_playwright_proxy():
    """
    Formata o proxy para o formato esperado pelo Playwright (com suporte a autenticação).
    """
    proxy_url = os.getenv("PROXY_HTTP")
    if not proxy_url:
        return None
    
    try:
        parsed = urlparse(proxy_url)
        proxy_config = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        }
        if parsed.username and parsed.password:
            proxy_config["username"] = parsed.username
            proxy_config["password"] = parsed.password
        return proxy_config
    except Exception as e:
        print(f"[WARN] Erro ao processar proxy para Playwright: {e}")
        return {"server": proxy_url}

def fetch_pdf(url: str) -> bytes:
    """
    Download robusto de arquivos PDF usando requests com proxy e headers realistas.
    """
    print(f"[FETCH] Baixando PDF via requests: {url}")
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    session.headers.update(headers)
    
    proxies = get_proxies()
    valid_proxies = {k: v for k, v in proxies.items() if v}
    
    response = session.get(
        url,
        proxies=valid_proxies if valid_proxies else None,
        timeout=30,
        stream=True,
        allow_redirects=True
    )
    
    if response.status_code != 200:
        raise Exception(f"Erro ao baixar PDF: HTTP {response.status_code}")
    
    content = response.content
    if not content.startswith(b"%PDF-"):
        # Se não começar com %PDF-, pode ser um HTML de erro mascarado
        if b"<html" in content.lower() or b"<!doctype html" in content.lower():
            raise Exception("O servidor retornou HTML em vez de um PDF (possível bloqueio ou erro).")
        raise Exception(f"O conteúdo baixado não é um PDF válido (Início: {content[:10]!r}).")
        
    return content

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extrai texto de bytes de um PDF usando PyMuPDF (fitz).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"[ERROR] Erro ao extrair texto do PDF: {e}")
        return ""

def fetch_with_requests(url: str) -> str:
    """
    Primeira tentativa de busca usando a biblioteca requests com proxy e headers realistas.
    """
    print("[FETCH] usando requests")
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }

    session.headers.update(headers)

    proxies = get_proxies()
    # Verifica se os proxies são válidos (não None ou string vazia)
    valid_proxies = {k: v for k, v in proxies.items() if v}
    
    response = session.get(
        url,
        proxies=valid_proxies if valid_proxies else None,
        timeout=15,
        allow_redirects=True
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    return response.text

def fetch_with_playwright(url: str) -> str:
    """
    Segunda tentativa (fallback) usando Playwright para sites com proteção anti-bot pesada.
    """
    print("[FETCH] fallback playwright")
    proxy_config = get_playwright_proxy()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_config,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        try:
            page = context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response:
                raise Exception("Playwright não recebeu resposta (response is None)")
                
            if response.status != 200:
                raise Exception(f"Playwright recebeu status HTTP {response.status}")
                
            content = page.content()
            
            # Verificação básica de conteúdo bloqueado (ex: Cloudflare, 403 Forbidden no body)
            lowered_content = content.lower()
            if "forbidden" in lowered_content or "access denied" in lowered_content or "cloudflare" in lowered_content:
                if len(content) < 2000: # Páginas de erro costumam ser curtas
                    raise Exception("Playwright detectou página de bloqueio ou erro")

            return content
        finally:
            browser.close()

def fetch_with_jina(url: str) -> str:
    """
    Terceira tentativa (fallback final) usando Jina Reader.
    """
    print("[FETCH] fallback jina reader")
    jina_url = f"https://r.jina.ai/{url}"
    response = requests.get(jina_url, timeout=15)
    
    if response.status_code != 200:
        raise Exception(f"Jina Reader falhou com status {response.status_code}")
        
    return response.text

def fetch_url_content(url: str) -> str:
    """
    Função principal com estratégia de fallback automático.
    Suporta também arquivos locais via file://.
    """
    url = url.strip()
    print(f"[FETCH] Iniciando busca para: {url}")
    
    if url.startswith("file://"):
        parsed = urlparse(url)
        filepath = parsed.path
        if not os.path.exists(filepath):
            raise Exception(f"Arquivo local não encontrado: {filepath}")
        
        if url.lower().endswith(".pdf"):
            with open(filepath, "rb") as f:
                pdf_bytes = f.read()
            return extract_text_from_pdf_bytes(pdf_bytes)
        else:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    # Roteamento para PDF remoto
    if url.lower().endswith(".pdf"):
        try:
            pdf_bytes = fetch_pdf(url)
            text = extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                print(f"[WARN] PDF baixado mas sem texto extraível: {url}")
            return text
        except Exception as e:
            print(f"[ERROR] Falha crítica ao processar PDF: {e}")
            raise Exception(f"Não foi possível processar o PDF: {e}")

    # Fluxo para HTML
    # 1. Requests
    try:
        return fetch_with_requests(url)
    except Exception as e:
        print(f"[WARN] Nível 1 (Requests) falhou: {e}. Tentando fallback...")

        # 2. Playwright
        try:
            return fetch_with_playwright(url)
        except Exception as e2:
            print(f"[WARN] Nível 2 (Playwright) falhou: {e2}. Tentando fallback final...")
            
            # 3. Jina Reader
            try:
                content = fetch_with_jina(url)
                # Verifica se o Jina não retornou uma página de erro 403 (comum no Jina também)
                if "403 forbidden" in content.lower() and len(content) < 500:
                    raise Exception("Jina Reader também recebeu 403 Forbidden")
                return content
            except Exception as e3:
                print(f"[ERROR] Todos os métodos de fetch falharam para {url}")
                raise Exception(f"Erro final ao acessar URL após todos os fallbacks: {e3}")
