import os
import requests
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def get_proxies():
    """
    Lê os proxies das variáveis de ambiente.
    """
    return {
        "http": os.getenv("PROXY_HTTP"),
        "https": os.getenv("PROXY_HTTPS"),
    }

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
    proxy_url = os.getenv("PROXY_HTTP")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={
                "server": proxy_url
            } if proxy_url else None,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        content = page.content()
        browser.close()

        return content

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
    """
    try:
        return fetch_with_requests(url)
    except Exception as e:
        print(f"[WARN] requests falhou: {e}")

        try:
            return fetch_with_playwright(url)
        except Exception as e2:
            print(f"[WARN] playwright falhou: {e2}")
            
            try:
                return fetch_with_jina(url)
            except Exception as e3:
                raise Exception(f"Erro final ao acessar URL após todos os fallbacks: {e3}")
