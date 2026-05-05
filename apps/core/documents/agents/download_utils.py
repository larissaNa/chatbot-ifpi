import os
import time
import logging
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import sync_playwright
from apps.core.utils.fetcher import get_proxies, get_playwright_proxy

# Configuração de Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_robust_session():
    """Configura uma sessão requests robusta."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def baixar_arquivo_resiliente(url: str) -> bytes:
    """
    Tenta baixar um arquivo usando requests com fallback para Playwright
    em caso de bloqueio anti-bot ou erro HTTP.
    Também suporta arquivos locais via file://.
    """
    if url.startswith("file://"):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # Extração robusta do caminho do arquivo local
        if parsed.netloc and os.name == 'nt' and parsed.netloc.endswith(':'):
            # Formato file://C:/path... -> netloc='C:', path='/path...'
            filepath = parsed.netloc + parsed.path
        elif parsed.path.startswith('/') and len(parsed.path) > 2 and parsed.path[2] == ':':
            # Formato file:///C:/path... -> path='/C:/path...'
            filepath = parsed.path[1:]
        else:
            # Linux ou caminhos relativos
            filepath = parsed.path if parsed.path else parsed.netloc

        # Normaliza o separador de caminho para o SO atual
        filepath = os.path.normpath(filepath)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    content = f.read()
                    if not content:
                        logger.warning(f"[DOWNLOAD] Arquivo local vazio: {filepath}")
                    return content
            except Exception as e:
                raise IOError(f"Erro ao ler arquivo local {filepath}: {e}")
        else:
            raise FileNotFoundError(f"Arquivo local não encontrado: {filepath}")

    proxies = get_proxies()
    # Verifica se os proxies são válidos
    valid_proxies = {k: v for k, v in proxies.items() if v} if proxies else None
    session = _get_robust_session()
    
    # 1. Tentativa com Requests
    try:
        resp = session.get(url, timeout=30, stream=True, proxies=valid_proxies)
        content = resp.content # Força leitura completa
        
        # Validação de Bloqueio
        is_valid = True
        if resp.status_code != 200:
            logger.warning(f"[DOWNLOAD] Status {resp.status_code} para {url}")
            is_valid = False
        
        content_type = resp.headers.get("Content-Type", "").lower()
        # Se for um PDF, faz validações extras. Se for outro tipo, confia mais no status 200.
        if "pdf" in content_type and len(content) < 2000:
            # Conteúdo pequeno que não é PDF geralmente é página de erro/captcha
            logger.warning(f"[DOWNLOAD] Conteúdo suspeito (Tipo: {content_type}, Tamanho: {len(content)})")
            is_valid = False
            
        if len(content) < 50: # Txts podem ser bem pequenos
            logger.warning(f"[DOWNLOAD] Conteúdo muito pequeno ({len(content)} bytes)")
            # Não marcamos como inválido se for 200 e não for PDF, pode ser um TXT curto
            if "pdf" in content_type:
                is_valid = False

        if is_valid:
            logger.info("[DOWNLOAD] requests sucesso")
            return content
            
    except Exception as e:
        logger.error(f"[DOWNLOAD] Erro no requests: {e}")

    # 2. Fallback para Playwright
    logger.info("[DOWNLOAD] bloqueado ou erro, usando playwright")
    
    try:
        proxy_config = get_playwright_proxy()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                proxy=proxy_config,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Contexto com Viewport e UserAgent realistas
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            # Intercepta o download ou navega diretamente para a URL
            # Para PDFs, o Playwright muitas vezes dispara um evento de download ou abre o PDF
            # Vamos tentar navegar e capturar o response
            
            response = page.goto(url, wait_until="networkidle", timeout=60000)
            
            if response and response.status == 200:
                pdf_bytes = response.body()
                
                # Validação mínima dos bytes do PDF (%PDF-)
                if pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000:
                    logger.info("[DOWNLOAD] playwright sucesso")
                    browser.close()
                    return pdf_bytes
                else:
                    logger.error(f"[DOWNLOAD] Playwright retornou conteúdo inválido para PDF ({len(pdf_bytes)} bytes)")
            
            browser.close()
            
    except Exception as e:
        logger.error(f"[DOWNLOAD] Falha no Playwright: {e}")

    logger.error("[DOWNLOAD] falha total")
    raise Exception(f"Não foi possível baixar o PDF da URL: {url}")
