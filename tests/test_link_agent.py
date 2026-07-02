import unittest
from unittest.mock import MagicMock, patch
import sys
import os

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from apps.core.documents.agents.link_analysis_agent import _analise_basica_url, analisar_link
except ImportError as e:
    sys.path.append(os.path.join(current_dir, "apps", "core", "documents", "agents"))
    from link_analysis_agent import _analise_basica_url, analisar_link

class TestLinkAnalysisAgent(unittest.TestCase):

    def test_analise_basica_pdf(self):
        """Testa se identifica corretamente um PDF direto"""
        print("\n[TESTE] Verificando identificação de PDF direto...")
        with patch("apps.core.documents.agents.link_analysis_agent.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.headers = {"Content-Type": "application/pdf"}

            url = "http://example.com/arquivo.pdf"
            print(f"   -> URL simulada: {url}")
            resultado = _analise_basica_url(url)

            self.assertEqual(resultado["tipo_conteudo"], "PDF_DIRETO")
            self.assertEqual(resultado["status"], "sucesso")
            print("   -> Sucesso: Identificado como PDF_DIRETO.")

    def test_analise_basica_html_com_pdf(self):
        """Testa se identifica HTML e encontra links de PDF"""
        print("\n[TESTE] Verificando identificação de HTML com links para PDF...")
        module_name = _analise_basica_url.__module__

        html_content = (
            "<html><head><title>Normas Institucionais</title></head>"
            "<body><a href=\"norma.pdf\">Baixar Norma</a>"
            "<p>Resolução do IFPI publicada.</p></body></html>"
        )

        with patch("apps.core.documents.agents.link_analysis_agent.requests.get") as mock_get, \
             patch(f"{module_name}.fetch_url_content", return_value=html_content):

            # GET inicial (verificação de acessibilidade) diz que é HTML
            mock_get.return_value.status_code = 200
            mock_get.return_value.headers = {"Content-Type": "text/html"}

            url = "http://example.com/normas"
            print(f"   -> URL simulada: {url}")
            resultado = _analise_basica_url(url)

            # Se o resultado for INVALIDO, significa que ocorreram exceções ou a lógica falhou.
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
