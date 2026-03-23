import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import uuid
import json

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


_MOCK_KEYS = [
    "requests",
    "bs4",
    "fitz",
    "sentence_transformers",
    "langchain_core",
    "langchain_core.tools",
    "langchain_text_splitters",
    "numpy",
    "apps.authentication",
    "apps.authentication.models",
    "apps.db",
]
_ORIGINAL_MODULES = {k: sys.modules.get(k) for k in _MOCK_KEYS}

sys.modules["requests"] = MagicMock()
sys.modules["bs4"] = MagicMock()
sys.modules["fitz"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.tools"] = MagicMock()
sys.modules["langchain_text_splitters"] = MagicMock()
sys.modules["numpy"] = MagicMock()

mock_auth = MagicMock()
sys.modules["apps.authentication"] = mock_auth
sys.modules["apps.authentication.models"] = MagicMock()
sys.modules["apps.db"] = MagicMock()

#mocks sentence_transformers
mock_st = MagicMock()
mock_embedding_result = MagicMock()
mock_embedding_result.tolist.return_value = [0.1, 0.2, 0.3]
mock_st.encode.return_value = mock_embedding_result

sys.modules["sentence_transformers"].SentenceTransformer.return_value = mock_st
sys.modules["sentence_transformers"].util.cos_sim.return_value = MagicMock(max=lambda axis: MagicMock(values=MagicMock(mean=lambda: 0.9, min=lambda: 0.8)))

def tool_decorator(func):
    return func
sys.modules["langchain_core.tools"].tool = tool_decorator

mock_splitter_instance = MagicMock()
mock_splitter_instance.split_text.return_value = ["Chunk 1 text", "Chunk 2 text"]
sys.modules["langchain_text_splitters"].RecursiveCharacterTextSplitter.return_value = mock_splitter_instance


try:
    from apps.core.agents.link_analysis_agent import _analise_basica_url
    from apps.core.agents.extraction_agent import extrair_conteudo
    from apps.core.agents.processing_agent import processar_conteudo
    from apps.core.agents.belief_revision_agent import revisar_crenca
except ImportError as e:
    print(f"CRITICAL ERROR importing agents: {e}")
    sys.exit(1)

# restaura módulos imediatamente para não poluir outros testes durante o discovery
for k, v in _ORIGINAL_MODULES.items():
    if v is None:
        sys.modules.pop(k, None)
    else:
        sys.modules[k] = v

# ==========================================
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
        
        # Mockar requests para internos do agente de extração
        with patch("apps.core.agents.extraction_agent.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b"%PDF-1.4..."
            
            # Mock fitz (PyMuPDF)
            with patch("apps.core.agents.extraction_agent.fitz.open") as mock_open:
                mock_page = MagicMock()
                mock_page.get_text.return_value = "Conteúdo de teste do documento oficial."
                mock_pdf = MagicMock()
                mock_pdf.__len__.return_value = 1
                mock_pdf.__iter__.return_value = [mock_page]
                mock_open.return_value = mock_pdf
                
                try:
                    extraction_output = extrair_conteudo(link_output)
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
                    "texto": "Artigo 1. Fica estabelecido que o teste passou.\n\nArtigo 2. Tudo ok.",
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
        

        try:
            processing_output = processar_conteudo(extraction_output)
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
            revision_output = revisar_crenca(belief_input)
            print("   -> Agente de Revisão executado com sucesso.")
        except Exception as e:
            self.fail(f"Agente de Revisão falhou: {e}")
            
        self.assertTrue(isinstance(revision_output, dict))
        self.assertIn("status_crenca", revision_output)
        self.assertIn("acao_recomendada", revision_output)
        
        print("   -> CONTRATO VÁLIDO: Saída do Processamento (transformada) compatível com Entrada da Revisão.")

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
