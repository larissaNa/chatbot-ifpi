import unittest
from unittest.mock import MagicMock, patch
import sys
import os

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.config"] = MagicMock()

sys.modules["apps.db"] = MagicMock()
sys.modules["flask_sqlalchemy"] = MagicMock()
sys.modules["apps.authentication"] = MagicMock()
sys.modules["apps.authentication.models"] = MagicMock()


import types
m_apps = types.ModuleType("apps")
m_apps.__path__ = [os.path.join(current_dir, "apps")] # Point to real directory
m_apps.db = MagicMock()
sys.modules["apps"] = m_apps


from apps.core.agents.chromadb_agent import executar_persistencia

class TestChromaDBAgent(unittest.TestCase):
    
    def setUp(self):
        # Resetar mocks
        self.mock_chroma = sys.modules["chromadb"]
        self.mock_client = MagicMock()
        self.mock_collection = MagicMock()
        
        self.mock_chroma.PersistentClient.return_value = self.mock_client
        self.mock_client.get_or_create_collection.return_value = self.mock_collection
        
    def test_manter(self):
        print("\n[TESTE] Verificando operação MANTER (Nenhuma alteração no banco)...")
        input_data = {
            "id_crenca": "doc_123",
            "acao_recomendada": "MANTER",
            "chunks_processados": [],
            "metadados_associados": {}
        }
        
        print(f"   -> Input simulado: {input_data['acao_recomendada']}")
        result = executar_persistencia.invoke({"dados_persistencia": input_data})
        
        self.assertEqual(result["acao_executada"], "MANTER")
        self.assertEqual(result["resultado"]["chunks_inseridos"], 0)
        self.assertEqual(result["status_banco"], "CONSISTENTE")
        self.mock_collection.delete.assert_not_called()
        self.mock_collection.add.assert_not_called()
        print("   -> Sucesso: Nenhuma operação de escrita realizada.")

    def test_remover(self):
        print("\n[TESTE] Verificando operação REMOVER (Exclusão de vetores)...")
        input_data = {
            "id_crenca": "doc_123",
            "acao_recomendada": "REMOVER",
            "chunks_processados": [],
            "metadados_associados": {}
        }
        
        print(f"   -> Input simulado: {input_data['acao_recomendada']} para id_crenca='doc_123'")
        result = executar_persistencia.invoke({"dados_persistencia": input_data})
        
        self.assertEqual(result["acao_executada"], "REMOVER")
        self.mock_collection.delete.assert_called_with(where={"id_crenca": "doc_123"})
        self.assertEqual(result["status_banco"], "CONSISTENTE")
        print("   -> Sucesso: Delete chamado corretamente no ChromaDB.")

    def test_atualizar(self):
        print("\n[TESTE] Verificando operação ATUALIZAR (Substituição de vetores)...")
        chunks = [
            {"page_content": "Texto 1", "embedding": [0.1, 0.2], "metadata": {"p": 1}},
            {"page_content": "Texto 2", "embedding": [0.3, 0.4], "metadata": {"p": 2}}
        ]
        input_data = {
            "id_crenca": "doc_123",
            "acao_recomendada": "ATUALIZAR",
            "chunks_processados": chunks,
            "metadados_associados": {"source": "test"}
        }
        
        print(f"   -> Input simulado: {input_data['acao_recomendada']} com {len(chunks)} chunks")
        result = executar_persistencia.invoke({"dados_persistencia": input_data})
        
        self.assertEqual(result["acao_executada"], "ATUALIZAR")

        self.mock_collection.delete.assert_called_with(where={"id_crenca": "doc_123"})
        self.mock_collection.add.assert_called()
        self.assertEqual(result["resultado"]["chunks_inseridos"], 2)
        
        call_args = self.mock_collection.add.call_args[1] # kwargs
        self.assertEqual(len(call_args["ids"]), 2)
        self.assertEqual(call_args["metadatas"][0]["id_crenca"], "doc_123")
        self.assertEqual(call_args["metadatas"][0]["source"], "test")
        print("   -> Sucesso: Delete executado e novos chunks inseridos com metadados corretos.")

if __name__ == "__main__":
    unittest.main()
