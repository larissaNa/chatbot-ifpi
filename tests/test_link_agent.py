import unittest
from unittest.mock import MagicMock, patch
import sys
import os

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Mock de dependencias externas
sys.modules["requests"] = MagicMock()
sys.modules["bs4"] = MagicMock()
sys.modules["apps.config"] = MagicMock()

# Mock de modulos internos de app 
sys.modules["apps.authentication"] = MagicMock()
sys.modules["apps.authentication.models"] = MagicMock()
sys.modules["apps.db"] = MagicMock()


# Mock de decorador para @tool
def tool_decorator(func):
    def wrapper(*args, **kwargs):
        if hasattr(func, "invoke"):
            return func.invoke(*args, **kwargs)
        return func(*args, **kwargs)
    wrapper.invoke = lambda x: func(x)
    return wrapper

sys.modules["langchain_core.tools"] = MagicMock()
sys.modules["langchain_core.tools"].tool = tool_decorator

import types
if "apps" not in sys.modules:
    m_apps = types.ModuleType("apps")
    m_apps.__path__ = [os.path.join(current_dir, "apps")]
    sys.modules["apps"] = m_apps


try:
    from apps.core.agents.link_analysis_agent import _analise_basica_url, analisar_link
except ImportError as e:
    sys.path.append(os.path.join(current_dir, "apps", "core", "agents"))
    from link_analysis_agent import _analise_basica_url, analisar_link

class TestLinkAnalysisAgent(unittest.TestCase):

    def test_analise_basica_pdf(self):
        """Testa se identifica corretamente um PDF direto"""
        print("\n[TESTE] Verificando identificação de PDF direto...")
        with patch("apps.core.agents.link_analysis_agent.requests.head") as mock_head:
            mock_head.return_value.status_code = 200
            mock_head.return_value.headers = {"Content-Type": "application/pdf"}
            
            url = "http://example.com/arquivo.pdf"
            print(f"   -> URL simulada: {url}")
            resultado = _analise_basica_url(url)
            
            self.assertEqual(resultado["tipo_conteudo"], "PDF_DIRETO")
            self.assertEqual(resultado["status"], "SUCESSO")
            print("   -> Sucesso: Identificado como PDF_DIRETO.")

    def test_analise_basica_html_com_pdf(self):
        """Testa se identifica HTML e encontra links de PDF"""
        print("\n[TESTE] Verificando identificação de HTML com links para PDF...")
        with patch.object(sys.modules["requests"], "head") as mock_head, \
             patch.object(sys.modules["requests"], "get") as mock_get, \
             patch("bs4.BeautifulSoup") as mock_bs: 
            
            # HEAD diz que é HTML
            mock_head.return_value.status_code = 200
            mock_head.return_value.headers = {"Content-Type": "text/html"}
            
            # GET retorna HTML com link para PDF
            mock_get.return_value.status_code = 200
            
            # Mock BeautifulSoup para simular um link encontrado
            mock_soup = MagicMock()
            mock_a = MagicMock()
            # Se o código usar link.get('href'), ele retornará "norma.pdf"
            mock_a.get.return_value = "norma.pdf" 
            # Se o código tratar link como dict como link['href'], precisamos suportar __getitem__
            mock_a.__getitem__.return_value = "norma.pdf"
            
            mock_a.get_text.return_value = "Baixar Norma"
            mock_soup.find_all.return_value = [mock_a]
            mock_soup.select.return_value = [mock_a]
            
            mock_bs.return_value = mock_soup
            
            url = "http://example.com/normas"
            print(f"   -> URL simulada: {url}")
            module_name = _analise_basica_url.__module__
            
            import urllib.parse
            with patch("urllib.parse.urljoin", side_effect=lambda base, url: base.rstrip('/') + '/' + url if 'http' not in url else url):
                 # Somente se o módulo estiver carregado 
                 if module_name in sys.modules:
                      with patch(f"{module_name}.BeautifulSoup", return_value=mock_soup):
                          resultado = _analise_basica_url(url)
                 else:
                      # Se o módulo não estiver carregado, usamos a função original
                      resultado = _analise_basica_url(url)
            
            # Se o resultado for INVALIDO, significa que ocorreram exceções ou a lógica falhou.
            # Geralmente INVALIDO significa que a requisição falhou ou o parser falhou.
            if resultado["tipo_conteudo"] == "INVALIDO":
                 print(f"\nDEBUG FAIL: {resultado}")
            
            self.assertEqual(resultado["tipo_conteudo"], "HTML_COM_PDF")
            self.assertEqual(len(resultado["pdfs_encontrados"]), 1)
            self.assertTrue(resultado["pdfs_encontrados"][0]["url"].endswith("norma.pdf"))
            print("   -> Sucesso: Identificado HTML e encontrado 1 PDF.")

    def test_tool_invoke(self):
        """Testa a chamada via interface do Tool"""
        print("\n[TESTE] Verificando invocação via @tool (LangChain)...")
        module_name = _analise_basica_url.__module__
        
        with patch(f"{module_name}._analise_basica_url") as mock_analise:
            mock_analise.return_value = {"status": "SUCESSO", "mock": True}            
            result = analisar_link.invoke({"url": "http://teste.com"})
            
            self.assertTrue(result["mock"])
            mock_analise.assert_called()
            args, _ = mock_analise.call_args
            self.assertTrue(args[0] == "http://teste.com" or args[0] == {"url": "http://teste.com"})
            print("   -> Sucesso: Tool invocou a função interna corretamente.")

if __name__ == "__main__":
    unittest.main()