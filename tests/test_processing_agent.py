import unittest
from unittest.mock import MagicMock, patch
import inspect
import sys
import os
import json

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Mock dependencias
sys.modules["sentence_transformers"] = MagicMock()
mock_st = MagicMock()
mock_st.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
sys.modules["sentence_transformers"].SentenceTransformer.return_value = mock_st

sys.modules["langchain_text_splitters"] = MagicMock()
mock_splitter = MagicMock()
mock_splitter.split_text.return_value = ["Chunk 1", "Chunk 2"]
sys.modules["langchain_text_splitters"].RecursiveCharacterTextSplitter.return_value = mock_splitter


# Mock para tool — replica o comportamento real do LangChain @tool.invoke,
# que desempacota um dict de entrada pelo nome do (único) parâmetro da função.
def tool_decorator(func):
    param_names = list(inspect.signature(func).parameters)

    def _invoke(x):
        if isinstance(x, dict) and len(param_names) == 1 and param_names[0] in x:
            return func(x[param_names[0]])
        return func(x)

    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.invoke = _invoke
    return wrapper

sys.modules["langchain_core.tools"] = MagicMock()
sys.modules["langchain_core.tools"].tool = tool_decorator

from apps.core.documents.agents.processing_agent import processar_conteudo

class TestProcessingAgent(unittest.TestCase):
    
    def test_processar_conteudo_sucesso(self):
        """Testa o fluxo normal de processamento"""
        print("\n[TESTE] Verificando processamento de conteúdo (Chunking + Embedding)...")
        mock_input = {
            "fonte": "http://example.com/doc.pdf",
            "documentos": [
                {
                    "titulo": "Resolução Teste",
                    "tipo": "application/pdf",
                    "conteudo": (
                        "Art. 1º Fica instituído o teste de processamento de conteúdo institucional. "
                        "Art. 2º O teste deve funcionar corretamente, gerando os chunks e embeddings esperados."
                    ),
                    "metadata": {"autor": "Reitor"}
                }
            ],
            "status": "sucesso"
        }
        
        print(f"   -> Input simulado: {len(mock_input['documentos'])} documento(s)")
        with patch("apps.core.documents.agents.processing_agent._split_semantic_chunks", return_value=["Chunk 1", "Chunk 2"]), patch(
            "apps.core.documents.agents.processing_agent._generate_embedding", return_value=[0.1, 0.2, 0.3]
        ):
            if hasattr(processar_conteudo, "invoke"):
                resultado = processar_conteudo.invoke({"extracao": mock_input})
            else:
                resultado = processar_conteudo(mock_input)
        
        self.assertEqual(resultado["status"], "sucesso")
        self.assertEqual(len(resultado["chunks"]), 2) # Mock split returns 2 chunks
        self.assertEqual(resultado["chunks"][0]["embedding"], [0.1, 0.2, 0.3])
        self.assertEqual(resultado["documento"], "Resolução Teste")
        self.assertEqual(resultado["proximo_agente"], "AGENTE_REVISAO_CRENCAS")
        print("   -> Sucesso: Chunks gerados, embeddings calculados.")

    def test_processar_conteudo_input_invalido(self):
        """Testa comportamento com input inválido"""
        print("\n[TESTE] Verificando tratamento de input inválido...")
        if hasattr(processar_conteudo, "invoke"):
            resultado = processar_conteudo.invoke({"extracao": {}})
        else:
            resultado = processar_conteudo({})
        self.assertEqual(resultado["status"], "erro")
        self.assertEqual(resultado["proximo_agente"], "NENHUM")
        print("   -> Sucesso: Retornou status de erro conforme esperado.")

if __name__ == "__main__":
    unittest.main()
