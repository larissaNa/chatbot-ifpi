import sys
import os
import json
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.core.documents.agents.belief_revision_agent import revisar_crenca

def generate_embedding_sets_variable(n_old, n_new, similarity, dim=384):
    """
    Gera dois conjuntos de embeddings (old com n_old chunks, new com n_new chunks)
    com similaridade de cosseno média exatamente igual a 'similarity',
    onde os chunks novos são ortogonais entre si e os antigos são variações direcionadas.
    """
    if similarity == 1.0 and n_old == n_new:
        # Vetores idênticos
        q, _ = np.linalg.qr(np.random.randn(dim, n_old))
        emb = [q[:, i].tolist() for i in range(n_old)]
        return emb, emb

    # Decomposição QR para gerar uma base ortonormal
    total_vectors = n_new + n_old
    q, _ = np.linalg.qr(np.random.randn(dim, total_vectors))
    
    emb_new = [q[:, i].tolist() for i in range(n_new)]
    emb_old = []
    
    for i in range(n_old):
        # Associa o chunk antigo i ao novo correspondente (ciclicamente se n_old != n_new)
        target_new_idx = i % n_new
        u = q[:, target_new_idx]
        
        # Vetor de variação ortogonal exclusivo do chunk antigo i
        orthogonal_w = q[:, n_new + i]
        
        if similarity == 1.0:
            v = u
        else:
            # v_i = s * u_target + sqrt(1 - s^2) * w_i
            v = similarity * u + np.sqrt(1.0 - similarity**2) * orthogonal_w
            
        emb_old.append(v.tolist())
        
    return emb_old, emb_new

def run_battery():
    print("=" * 60)
    print("INICIANDO VALIDAÇÃO EXPERIMENTAL DO MECANISMO DE REVISÃO (41 CASOS)")
    print("=" * 60)

    cases = [
        # === 1. Documentos Inalterados (5 casos) ===
        {"id": 1, "categoria": "Documentos Inalterados", "n_old": 1, "n_new": 1, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 2, "categoria": "Documentos Inalterados", "n_old": 5, "n_new": 5, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 3, "categoria": "Documentos Inalterados", "n_old": 10, "n_new": 10, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 4, "categoria": "Documentos Inalterados", "n_old": 15, "n_new": 15, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 5, "categoria": "Documentos Inalterados", "n_old": 20, "n_new": 20, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        
        # === 2. Pequenas Alterações Textuais (5 casos) ===
        {"id": 6, "categoria": "Pequenas Alterações", "n_old": 3, "n_new": 3, "sim": 0.98, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 7, "categoria": "Pequenas Alterações", "n_old": 5, "n_new": 5, "sim": 0.96, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 8, "categoria": "Pequenas Alterações", "n_old": 1, "n_new": 1, "sim": 0.955, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 9, "categoria": "Pequenas Alterações", "n_old": 8, "n_new": 8, "sim": 0.975, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 10, "categoria": "Pequenas Alterações", "n_old": 12, "n_new": 12, "sim": 0.965, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        
        # === 3. Alterações Moderadas (5 casos) ===
        {"id": 11, "categoria": "Alterações Moderadas", "n_old": 3, "n_new": 3, "sim": 0.92, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 12, "categoria": "Alterações Moderadas", "n_old": 5, "n_new": 5, "sim": 0.88, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 13, "categoria": "Alterações Moderadas", "n_old": 1, "n_new": 1, "sim": 0.86, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 14, "categoria": "Alterações Moderadas", "n_old": 8, "n_new": 8, "sim": 0.91, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 15, "categoria": "Alterações Moderadas", "n_old": 12, "n_new": 12, "sim": 0.87, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        
        # === 4. Alterações Significativas (5 casos) ===
        {"id": 16, "categoria": "Alterações Significativas", "n_old": 3, "n_new": 3, "sim": 0.80, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        {"id": 17, "categoria": "Alterações Significativas", "n_old": 5, "n_new": 5, "sim": 0.70, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        {"id": 18, "categoria": "Alterações Significativas", "n_old": 1, "n_new": 1, "sim": 0.60, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        {"id": 19, "categoria": "Alterações Significativas", "n_old": 8, "n_new": 8, "sim": 0.75, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        {"id": 20, "categoria": "Alterações Significativas", "n_old": 15, "n_new": 15, "sim": 0.50, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        
        # === 5. Mudanças Estruturais / Variação de Chunks (6 casos) ===
        {"id": 21, "categoria": "Mudanças Estruturais", "n_old": 10, "n_new": 7, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 22, "categoria": "Mudanças Estruturais", "n_old": 5, "n_new": 3, "sim": 0.98, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 23, "categoria": "Mudanças Estruturais", "n_old": 5, "n_new": 7, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 24, "categoria": "Mudanças Estruturais", "n_old": 10, "n_new": 13, "sim": 0.98, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 25, "categoria": "Mudanças Estruturais", "n_old": 8, "n_new": 5, "sim": 0.96, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 26, "categoria": "Mudanças Estruturais", "n_old": 6, "n_new": 9, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        
        # === 6. Fontes Inacessíveis / Documentos Obsoletos (5 casos) ===
        {"id": 27, "categoria": "Fontes Inacessíveis", "n_old": 3, "n_new": 3, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/old.pdf", "status": "INVALIDO"}], "exp_status": "OBSOLETA", "exp_acao": "SINALIZAR_OBSOLESCENCIA", "exp_grau": "alto"},
        {"id": 28, "categoria": "Fontes Inacessíveis", "n_old": 3, "n_new": 3, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/old.pdf", "status": "VALIDO", "http_status": 404}], "exp_status": "OBSOLETA", "exp_acao": "SINALIZAR_OBSOLESCENCIA", "exp_grau": "alto"},
        {"id": 29, "categoria": "Fontes Inacessíveis", "n_old": 3, "n_new": 3, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/old.pdf", "status": "VALIDO", "http_status": 500}], "exp_status": "OBSOLETA", "exp_acao": "SINALIZAR_OBSOLESCENCIA", "exp_grau": "alto"},
        {"id": 30, "categoria": "Fontes Inacessíveis", "n_old": 5, "n_new": 5, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/old.pdf", "status": "INVALIDO", "http_status": 403}], "exp_status": "OBSOLETA", "exp_acao": "SINALIZAR_OBSOLESCENCIA", "exp_grau": "alto"},
        {"id": 31, "categoria": "Fontes Inacessíveis", "n_old": 10, "n_new": 10, "sim": 1.0, "fontes": [{"url": "http://ifpi.edu.br/old.pdf", "status": "VALIDO", "http_status": 503}], "exp_status": "OBSOLETA", "exp_acao": "SINALIZAR_OBSOLESCENCIA", "exp_grau": "alto"},
        
        # === 7. Casos de Fronteira / Limiares (10 casos) ===
        {"id": 32, "categoria": "Casos de Fronteira", "n_old": 3, "n_new": 3, "sim": 0.8501, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 33, "categoria": "Casos de Fronteira", "n_old": 3, "n_new": 3, "sim": 0.8499, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "alto"},
        {"id": 34, "categoria": "Casos de Fronteira", "n_old": 3, "n_new": 3, "sim": 0.9501, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 35, "categoria": "Casos de Fronteira", "n_old": 3, "n_new": 3, "sim": 0.9499, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 36, "categoria": "Casos de Fronteira", "n_old": 10, "n_new": 8, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 37, "categoria": "Casos de Fronteira", "n_old": 10, "n_new": 7, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 38, "categoria": "Casos de Fronteira", "n_old": 10, "n_new": 12, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 39, "categoria": "Casos de Fronteira", "n_old": 10, "n_new": 13, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "ATUALIZADA", "exp_acao": "ATUALIZAR", "exp_grau": "medio"},
        {"id": 40, "categoria": "Casos de Fronteira", "n_old": 5, "n_new": 4, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
        {"id": 41, "categoria": "Casos de Fronteira", "n_old": 5, "n_new": 6, "sim": 0.97, "fontes": [{"url": "http://ifpi.edu.br/doc.pdf", "status": "OK"}], "exp_status": "INALTERADA", "exp_acao": "MANTER", "exp_grau": "baixo"},
    ]

    total_casos = len(cases)
    acertos = 0
    erros = 0

    # Estruturas para estatísticas
    stats_categoria = {}
    classes = ["INALTERADA", "ATUALIZADA", "OBSOLETA"]
    confusion_matrix = {real: {pred: 0 for pred in classes} for real in classes}

    print(f"{'ID':<4} | {'Categoria':<25} | {'Sim':<6} | {'Vol. (O->N)':<11} | {'Esperado':<11} | {'Obtido':<11} | {'Resultado':<9}")
    print("-" * 90)

    for c in cases:
        emb_old, emb_new = generate_embedding_sets_variable(c["n_old"], c["n_new"], c["sim"])
        
        input_data = {
            "id_crenca": f"crenca-bateria-{c['id']:03d}",
            "texto_crenca": f"Crença de teste {c['id']}",
            "documentos_fonte": c["fontes"],
            "embeddings_anteriores": emb_old,
            "embeddings_atualizados": emb_new
        }
        
        # Invoca o agente
        res = revisar_crenca.invoke({"dados_revisao": input_data})
        
        status_obtido = res["status_crenca"]
        acao_obtida = res["acao_recomendada"]
        grau_obtido = res.get("grau_mudanca", "n/a")
        
        # Validação do acerto (status + ação recomendada + grau se aplicável)
        is_correct = (status_obtido == c["exp_status"] and 
                      acao_obtida == c["exp_acao"] and 
                      (status_obtido == "OBSOLETA" or grau_obtido == c["exp_grau"]))
        
        resultado_str = "SUCESSO" if is_correct else "FALHA"
        
        if is_correct:
            acertos += 1
        else:
            erros += 1
            
        # Matriz de Confusão
        if c["exp_status"] in classes and status_obtido in classes:
            confusion_matrix[c["exp_status"]][status_obtido] += 1
            
        # Estatísticas por Categoria
        cat = c["categoria"]
        if cat not in stats_categoria:
            stats_categoria[cat] = {"casos": 0, "acertos": 0, "erros": 0}
        stats_categoria[cat]["casos"] += 1
        if is_correct:
            stats_categoria[cat]["acertos"] += 1
        else:
            stats_categoria[cat]["erros"] += 1
            
        print(f"{c['id']:<4} | {c['categoria']:<25} | {c['sim']:<6.4f} | {c['n_old']:>3} -> {c['n_new']:<3} | {c['exp_status']:<11} | {status_obtido:<11} | {resultado_str:<9}")

    print("\n" + "=" * 60)
    print("MÉTRICAS CONSOLIDADAS")
    print("=" * 60)
    
    acuracia_global = acertos / total_casos
    print(f"Acurácia Global: {acuracia_global * 100:.2f}% ({acertos}/{total_casos})")
    
    print("\nDesempenho por Categoria:")
    print(f"{'Categoria':<25} | {'Casos':<6} | {'Acertos':<8} | {'Erros':<6} | {'Acurácia':<8}")
    print("-" * 65)
    for cat, info in stats_categoria.items():
        acc = info["acertos"] / info["casos"]
        print(f"{cat:<25} | {info['casos']:<6} | {info['acertos']:<8} | {info['erros']:<6} | {acc * 100:.2f}%")

    print("\nMatriz de Classificação (Confusão) - Status:")
    print(f"{'Real / Previsto':<16} | {'INALTERADA':<10} | {'ATUALIZADA':<10} | {'OBSOLETA':<10}")
    print("-" * 55)
    for real in classes:
        print(f"{real:<16} | {confusion_matrix[real]['INALTERADA']:<10} | {confusion_matrix[real]['ATUALIZADA']:<10} | {confusion_matrix[real]['OBSOLETA']:<10}")
        
    print("\nFim da Bateria!")
    
    # Assert global para garantir que o script de teste falhe caso haja alguma regressão
    assert erros == 0, f"Erro: {erros} caso(s) de teste falharam!"

if __name__ == "__main__":
    run_battery()
