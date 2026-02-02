import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Adiciona o diretório raiz ao path para importação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.core.agents.link_analysis_agent import analisar_link
from apps.core.agents.extraction_agent import extrair_conteudo

class TestHtmlExtraction(unittest.TestCase):
    
    @patch('apps.core.agents.link_analysis_agent.requests')
    @patch('apps.core.agents.link_analysis_agent.DocumentoOficial')
    @patch('apps.core.agents.link_analysis_agent.db')
    def test_analise_html_puro(self, mock_db, mock_doc_model, mock_requests):
        # Mock HEAD response
        mock_head = MagicMock()
        mock_head.status_code = 200
        mock_head.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_requests.head.return_value = mock_head
        
        # Mock GET response (HTML without PDFs)
        html_content = """
        <html>
            <head><title>Página de Teste</title></head>
            <body>
                <h1>Conteúdo Importante</h1>
                <p>Este é um texto de exemplo para testar a extração de HTML puro.</p>
                <p>Devemos garantir que o sistema aceite este conteúdo mesmo sem PDFs.</p>
                <p>O texto precisa ser longo o suficiente para passar no filtro de 300 caracteres se houver.</p>
                <p>Repetindo texto para volume... """ + ("bla " * 100) + """</p>
            </body>
        </html>
        """
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.text = html_content
        mock_requests.get.return_value = mock_get
        
        # Run Link Analysis
        print("\n--- Testando Análise de Link (HTML Puro) ---")
        resultado_analise = analisar_link.invoke({"url": "http://example.com/page"})
        print(f"Resultado Análise: {resultado_analise}")
        
        self.assertEqual(resultado_analise['status'], 'SUCESSO')
        self.assertEqual(resultado_analise['tipo_conteudo'], 'HTML_TEXTO')
        
        # Run Extraction
        print("\n--- Testando Extração de Conteúdo ---")
        
        # Mock requests inside extraction agent as well
        with patch('apps.core.agents.extraction_agent.requests') as mock_req_extract:
            mock_req_extract.get.return_value = mock_get
            resultado_extracao = extrair_conteudo.invoke({"analise": resultado_analise})
            
        print(f"Resultado Extração: {resultado_extracao}")
        
        self.assertEqual(resultado_extracao['tipo_extracao'], 'HTML')
        self.assertTrue(len(resultado_extracao['documentos']) > 0)
        self.assertIn("Conteúdo Importante", resultado_extracao['documentos'][0]['texto'])

    @patch('apps.core.agents.link_analysis_agent.requests')
    @patch('apps.core.agents.link_analysis_agent.DocumentoOficial')
    @patch('apps.core.agents.link_analysis_agent.db')
    def test_analise_html_limite(self, mock_db, mock_doc_model, mock_requests):
        # Mock HEAD response
        mock_head = MagicMock()
        mock_head.status_code = 200
        mock_head.headers = {"Content-Type": "text/html"}
        mock_requests.head.return_value = mock_head
        
        # HTML com ~60 caracteres (acima de 50, abaixo de 300)
        texto_60_chars = "Este é um texto curto mas suficiente para ser aceito. " + ("x" * 10)
        html_content = f"<html><body><p>{texto_60_chars}</p></body></html>"
        
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.text = html_content
        mock_requests.get.return_value = mock_get
        
        # Run Link Analysis
        print("\n--- Testando Análise de Link (Limite 50 chars) ---")
        resultado_analise = analisar_link.invoke({"url": "http://example.com/limit"})
        print(f"Resultado Análise: {resultado_analise}")
        
        self.assertEqual(resultado_analise['status'], 'SUCESSO')
        self.assertEqual(resultado_analise['tipo_conteudo'], 'HTML_TEXTO')
        self.assertEqual(resultado_analise['proximo_agente'], 'AGENTE_EXTRACAO')
        
if __name__ == '__main__':
    unittest.main()
