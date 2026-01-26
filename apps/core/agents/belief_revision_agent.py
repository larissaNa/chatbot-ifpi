from langchain_core.tools import tool
from datetime import datetime
import json
import numpy as np
from sentence_transformers import util

@tool
def revisar_crenca(dados_revisao: dict) -> dict:
    """
    Revisa uma crença institucional comparando embeddings antigos e novos para detectar mudanças.
    
    Args:
        dados_revisao (dict): Dicionário contendo:
            - id_crenca (str): ID da crença.
            - texto_crenca (str): Texto da crença.
            - documentos_fonte (list): Lista de documentos fonte com status.
            - embeddings_anteriores (list): Lista de vetores (floats) da versão anterior.
            - embeddings_atualizados (list): Lista de vetores (floats) da nova versão processada.
            
    Returns:
        dict: Resultado da revisão com status, ação recomendada e justificativa.
    """
    
    # 1. Extração de dados
    id_crenca = dados_revisao.get("id_crenca")
    docs_fonte = dados_revisao.get("documentos_fonte", [])
    emb_old = dados_revisao.get("embeddings_anteriores", [])
    # Tenta pegar chunks completos ou apenas embeddings
    chunks_novos = dados_revisao.get("chunks_novos", []) 
    if chunks_novos:
        # Se temos chunks completos, extraímos os embeddings deles se não fornecidos explicitamente
        if not dados_revisao.get("embeddings_atualizados"):
            emb_new = [c.get("embedding") for c in chunks_novos if c.get("embedding")]
        else:
            emb_new = dados_revisao.get("embeddings_atualizados", [])
    else:
        emb_new = dados_revisao.get("embeddings_atualizados", [])
    
    metadados_globais = dados_revisao.get("metadados_associados", {})

    # Validação básica
    if not id_crenca:
        return {"erro": "ID da crença não fornecido"}

    # 2. Verificação de Integridade das Fontes
    # Se alguma fonte crítica estiver inacessível/removida, sinalizar
    fontes_removidas = [d for d in docs_fonte if d.get("status") == "INVALIDO" or d.get("http_status", 200) != 200]
    
    if fontes_removidas:
        return {
            "id_crenca": id_crenca,
            "status_crenca": "OBSOLETA", # Indica que o conteúdo pode estar desatualizado
            "grau_mudanca": "alto",
            "documentos_afetados": [{"fonte": d.get("url"), "tipo_mudanca": "remocao"} for d in fontes_removidas],
            "acao_recomendada": "SINALIZAR_OBSOLESCENCIA", # Mudança: não remover automaticamente
            "chunks_processados": [], 
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": f"Fontes originais inacessíveis: {[d.get('url') for d in fontes_removidas]}. Aguardando confirmação do administrador.",
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "AGENTE_CHROMADB"
        }

    # Se não há novos embeddings (e as fontes estão ok), algo falhou no processamento ou o documento está vazio
    if not emb_new:
        return {
            "id_crenca": id_crenca,
            "status_crenca": "INALTERADA", # Conservador: se não conseguiu processar, mantém (ou sinaliza erro)
            "grau_mudanca": "baixo",
            "documentos_afetados": [],
            "acao_recomendada": "MANTER",
            "chunks_processados": [],
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": "Não foram gerados novos embeddings para comparação (possível falha de processamento ou documento vazio). Mantendo estado atual por cautela.",
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "NENHUM"
        }
        
    if len(emb_old) == 0:
         # Se não tinha embeddings antes, é uma "atualização" (ou criação inicial tratada como revisão)
         return {
            "id_crenca": id_crenca,
            "status_crenca": "ATUALIZADA",
            "grau_mudanca": "alto",
            "documentos_afetados": [],
            "acao_recomendada": "ATUALIZAR",
            "chunks_processados": chunks_novos,
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": "Não havia embeddings anteriores registrados. Atualização inicial.",
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "AGENTE_CHROMADB"
        }

    # 3. Comparação Semântica
    # Calcula similaridade de cosseno entre o conjunto antigo e o novo
    # Como são listas de chunks, comparamos a similaridade média ou máxima
    
    # Convertendo para tensores/arrays se necessário (util.cos_sim espera tensores ou listas de listas)
    # Calculando matriz de similaridade: Old x New
    try:
        # Garante que ambos sejam arrays numpy do mesmo tipo (float32) para evitar erro de dtype
        emb_old_np = np.array(emb_old, dtype=np.float32)
        emb_new_np = np.array(emb_new, dtype=np.float32)
        
        sim_matrix = util.cos_sim(emb_old_np, emb_new_np)
        # Para cada chunk antigo, qual o chunk novo mais similar?
        # Se o documento é o mesmo, esperamos que cada chunk antigo tenha um correspondente novo muito similar.
        # Se o texto mudou, a similaridade máxima vai cair.
        
        max_similarities = sim_matrix.max(axis=1).values # Tensor com a melhor similaridade para cada chunk antigo
        avg_similarity = float(max_similarities.mean())
        min_similarity = float(max_similarities.min())
        
    except Exception as e:
        return {"erro": f"Falha no cálculo de similaridade: {str(e)}"}

    # 4. Classificação Baseada em Limiares
    # Limiares heurísticos (ajustáveis)
    LIMIAR_CRITICO = 0.85  # Abaixo disso, mudança significativa
    LIMIAR_ALERTA = 0.95   # Abaixo disso, pequena mudança
    
    status = "INALTERADA"
    grau = "baixo"
    acao = "MANTER"
    justificativa = f"Similaridade semântica média de {avg_similarity:.4f}."

    if avg_similarity < LIMIAR_CRITICO:
        status = "ATUALIZADA"
        grau = "alto"
        acao = "ATUALIZAR"
        justificativa = f"Detectada mudança semântica relevante. Similaridade média caiu para {avg_similarity:.4f} (mínima: {min_similarity:.4f})."
    elif avg_similarity < LIMIAR_ALERTA:
        status = "ATUALIZADA"
        grau = "medio"
        acao = "ATUALIZAR"
        justificativa = f"Detectada mudança semântica moderada. Similaridade média: {avg_similarity:.4f}."
    else:
        # Verifica se o número de chunks mudou drasticamente (adição/remoção de conteúdo)
        len_old = len(emb_old)
        len_new = len(emb_new)
        ratio = len_new / len_old if len_old > 0 else 0
        
        if ratio < 0.8 or ratio > 1.2:
             status = "ATUALIZADA"
             grau = "medio"
             acao = "ATUALIZAR"
             justificativa = f"Conteúdo semântico similar, mas volume de informação mudou significativamente (Chunks: {len_old} -> {len_new})."

    # 5. Montagem da Saída
    return {
        "id_crenca": id_crenca,
        "status_crenca": status,
        "grau_mudanca": grau,
        "documentos_afetados": [{"fonte": d.get("url"), "tipo_mudanca": "conteudo"} for d in docs_fonte], # Simplificado
        "acao_recomendada": acao,
        "chunks_processados": chunks_novos if acao == "ATUALIZAR" else [],
        "metadados_associados": metadados_globais,
        "justificativa_tecnica": justificativa,
        "timestamp_revisao": datetime.now().isoformat(),
        "proximo_agente": "AGENTE_CHROMADB" if acao != "MANTER" else "NENHUM"
    }
