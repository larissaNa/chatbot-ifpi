import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import uuid
import json

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from apps.core.documents.agents.link_analysis_agent import _analise_basica_url
from apps.core.documents.agents.extraction_agent import extrair_conteudo
from apps.core.documents.agents.processing_agent import processar_conteudo
from apps.core.documents.agents.belief_revision_agent import revisar_crenca

# TESTES
# ==========================================

class TestAgentPipelineIO(unittest.TestCase):
    
    def test_01_link_analysis_to_extraction(self):
        print("\n[TESTE] 1. Análise de Links -> Agente de Extração")
        
        # Simular a saída da análise de links (imitando o retorno de _analise_basica_url)
        link_output = {
            "url": "http://example.com/doc.pdf",
            "status": "SUCESSO",
            "tipo_conteudo": "PDF_DIRETO",
            "titulo": "Resolução Teste",
            "pdfs_encontrados": [],
            "observacoes": "PDF direto encontrado.",
            "proximo_agente": "AGENTE_EXTRACAO"
        }
        
        print(f"   -> Chaves de Saída (Link): {list(link_output.keys())}")
        
        # Verificar a compatibilidade da entrada do agente de extração
        # extrair_conteudo espera um dict com chaves: 'url'/'fonte', 'tipo_conteudo', 'pdfs_encontrados', 'titulo'
        
        # Mockar baixar_arquivo_resiliente para retornar bytes simulados de PDF
        with patch("apps.core.documents.agents.extraction_agent.baixar_arquivo_resiliente", return_value=b"%PDF-1.4...") as mock_download:
            # Mock fitz (PyMuPDF)
            with patch("apps.core.documents.agents.extraction_agent.fitz.open") as mock_open:
                mock_page = MagicMock()
                mock_page.get_text.side_effect = lambda format="text": (
                    [(0, 0, 100, 100, "Conteúdo de teste do documento oficial. " * 20, 0, 0)]
                    if format == "blocks"
                    else "Conteúdo de teste do documento oficial. " * 20
                )
                mock_page.find_tables.return_value = MagicMock(tables=[])
                
                mock_pdf = MagicMock()
                mock_pdf.__len__.return_value = 1
                mock_pdf.__iter__.return_value = [mock_page]
                mock_open.return_value = mock_pdf
                
                try:
                    extraction_output = extrair_conteudo.invoke({"analise": link_output})
                    print("   -> Agente de Extração executado com sucesso.")
                except Exception as e:
                    self.fail(f"Agente de Extração falhou com saída da Análise de Links: {e}")
        
        self.extraction_output = extraction_output
        self.assertTrue(isinstance(extraction_output, dict))
        self.assertEqual(extraction_output["proximo_agente"], "AGENTE_PROCESSAMENTO")
        print("   -> CONTRATO VÁLIDO: Saída da Análise de Links compatível com Entrada da Extração.")

    def test_02_extraction_to_processing(self):
        print("\n[TESTE] 2. Agente de Extração -> Agente de Processamento")
        
        # Simular a saída do agente de extração (imitando o retorno de extrair_conteudo)
        extraction_output = {
            "fonte": "http://example.com/doc.pdf",
            "tipo_extracao": "PDF_TEXTUAL",
            "documentos": [
                {
                    "id_documento": "123",
                    "titulo": "Resolução Teste",
                    "texto": "Artigo 1. Fica estabelecido que o teste passou.\n\nArtigo 2. Tudo ok. " * 20,
                    "metadata": {
                        "paginas_estimadas": 1,
                        "idioma": "pt",
                        "tipo_extracao": "PDF_TEXTUAL"
                    }
                }
            ],
            "observacoes": "",
            "proximo_agente": "AGENTE_PROCESSAMENTO"
        }
        
        print(f"   -> Chaves de Saída (Extração): {list(extraction_output.keys())}")
        print(f"   -> Chaves do Documento: {list(extraction_output['documentos'][0].keys())}")
        

        with patch("apps.core.documents.agents.processing_agent._split_semantic_chunks", return_value=["Chunk 1 text", "Chunk 2 text"]), \
             patch("apps.core.documents.agents.processing_agent._generate_embedding", return_value=[0.1, 0.2, 0.3]):
            try:
                processing_output = processar_conteudo.invoke({"extracao": extraction_output})
                print("   -> Agente de Processamento executado com sucesso.")
            except Exception as e:
                self.fail(f"Agente de Processamento falhou com saída da Extração: {e}")
            
        self.processing_output = processing_output
        self.assertTrue(isinstance(processing_output, dict))
        self.assertEqual(processing_output["status"], "sucesso")
        self.assertTrue("chunks" in processing_output)
        self.assertTrue(len(processing_output["chunks"]) > 0)
        
        chunk_meta = processing_output["chunks"][0]["metadata"]
        self.assertIn("paginas_estimadas", chunk_meta, "Metadata 'paginas_estimadas' perdida!")
        self.assertIn("idioma", chunk_meta, "Metadata 'idioma' perdida!")
        
        print("   -> CONTRATO VÁLIDO: Saída da Extração compatível com Entrada do Processamento.")

    def test_03_processing_to_belief_revision(self):
        print("\n[TESTE] 3. Agente de Processamento -> Agente de Revisão de Crenças")
        
        # Simular saída de processamento
        processing_output = {
            "fonte": "http://example.com/doc.pdf",
            "documento": "Resolução Teste",
            "chunks": [
                {
                    "page_content": "Artigo 1...",
                    "metadata": {"chunk_id": "c1"},
                    "embedding": [0.1, 0.2, 0.3]
                },
                {
                    "page_content": "Artigo 2...",
                    "metadata": {"chunk_id": "c2"},
                    "embedding": [0.4, 0.5, 0.6]
                }
            ],
            "total_chunks": 2,
            "proximo_agente": "AGENTE_REVISAO_CRENCAS",
            "status": "sucesso"
        }
        
        
# Construir a entrada do agente de revisão de conclusão
        new_embeddings = [c["embedding"] for c in processing_output["chunks"]]
        
        belief_input = {
            "id_crenca": "crenca_123",
            "texto_crenca": "Texto da crença antiga",
            "documentos_fonte": [{"url": "http://example.com/doc.pdf", "status": "OK"}],
            "embeddings_anteriores": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], # Mock old embeddings
            "embeddings_atualizados": new_embeddings
        }
        
        print(f"   -> Chaves de Entrada Construídas (Revisão): {list(belief_input.keys())}")
        
        try:
            revision_output = revisar_crenca.invoke({"dados_revisao": belief_input})
            print("   -> Agente de Revisão executado com sucesso.")
        except Exception as e:
            self.fail(f"Agente de Revisão falhou: {e}")
            
        self.assertTrue(isinstance(revision_output, dict))
        self.assertIn("status_crenca", revision_output)
        self.assertIn("acao_recomendada", revision_output)
        
        print("   -> CONTRATO VÁLIDO: Saída do Processamento (transformada) compatível com Entrada da Revisão.")

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
