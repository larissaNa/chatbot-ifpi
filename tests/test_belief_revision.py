import sys
import os
import json
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.core.documents.agents.belief_revision_agent import revisar_crenca

def generate_embedding(dim=384):
    """Gera um vetor normalizado aleatório"""
    vec = np.random.rand(dim)
    return (vec / np.linalg.norm(vec)).tolist()

def test_belief_revision():
    print("=== Teste do Agente de Revisão de Crenças ===")
    
    # Caso 1: Sem mudança (Embeddings idênticos)
    emb_base = [generate_embedding() for _ in range(3)]
    
    input_inalterada = {
        "id_crenca": "crenca-001",
        "texto_crenca": "O IFPI possui campus em Teresina.",
        "documentos_fonte": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}],
        "embeddings_anteriores": emb_base,
        "embeddings_atualizados": emb_base # Mesmos embeddings
    }
    
    print("\n1. Testando Caso INALTERADA...")
    res1 = revisar_crenca.invoke({"dados_revisao": input_inalterada})
    print(json.dumps(res1, indent=2, ensure_ascii=False))
    assert res1["status_crenca"] == "INALTERADA"
    assert res1["acao_recomendada"] == "MANTER"

    # Caso 2: Mudança Semântica (Embeddings diferentes)
    emb_new = [generate_embedding() for _ in range(3)] # Vetores aleatórios serão distantes
    
    input_atualizada = {
        "id_crenca": "crenca-002",
        "texto_crenca": "O reitor é Fulano.",
        "documentos_fonte": [{"url": "http://ifpi.edu.br/reitor.pdf", "status": "OK"}],
        "embeddings_anteriores": emb_base,
        "embeddings_atualizados": emb_new
    }
    
    print("\n2. Testando Caso ATUALIZADA (Mudança de Conteúdo)...")
    res2 = revisar_crenca.invoke({"dados_revisao": input_atualizada})
    print(json.dumps(res2, indent=2, ensure_ascii=False))
    # Vetores aleatórios em alta dimensão tendem a ter baixa similaridade
    assert res2["status_crenca"] == "ATUALIZADA"
    assert res2["acao_recomendada"] == "ATUALIZAR"

    # Caso 3: Fonte Removida
    input_obsoleta = {
        "id_crenca": "crenca-003",
        "texto_crenca": "Norma antiga.",
        "documentos_fonte": [{"url": "http://ifpi.edu.br/old.pdf", "status": "INVALIDO"}],
        "embeddings_anteriores": emb_base,
        "embeddings_atualizados": []
    }
    
    print("\n3. Testando Caso OBSOLETA (Fonte Removida)...")
    res3 = revisar_crenca.invoke({"dados_revisao": input_obsoleta})
    print(json.dumps(res3, indent=2, ensure_ascii=False))
    assert res3["status_crenca"] == "OBSOLETA"
    assert res3["acao_recomendada"] == "SINALIZAR_OBSOLESCENCIA"
    
    print("\nTodos os testes passaram com sucesso!")

if __name__ == "__main__":
    test_belief_revision()
