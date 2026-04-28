import os
from datetime import datetime

import numpy as np
from langchain_core.tools import tool

ENV = os.getenv("ENV", "dev")


def _calculate_cosine_similarity(vec_a, vec_b):
    """
    Calcula a similaridade de cosseno entre dois conjuntos de vetores sem depender de sentence_transformers.
    vec_a, vec_b: numpy arrays (n_samples, n_features)
    Retorna uma matriz de similaridade.
    """
    # Normalização dos vetores (L2 norm)
    norm_a = np.linalg.norm(vec_a, axis=1, keepdims=True)
    norm_b = np.linalg.norm(vec_b, axis=1, keepdims=True)

    # Evitar divisão por zero
    norm_a[norm_a == 0] = 1.0
    norm_b[norm_b == 0] = 1.0

    vec_a_norm = vec_a / norm_a
    vec_b_norm = vec_b / norm_b

    # Produto escalar dos vetores normalizados
    return np.dot(vec_a_norm, vec_b_norm.T)


@tool
def revisar_crenca(dados_revisao: dict) -> dict:
    """
    Revisa uma crenca institucional comparando embeddings antigos e novos
    para detectar mudancas semanticas.
    """
    id_crenca = dados_revisao.get("id_crenca")
    docs_fonte = dados_revisao.get("documentos_fonte", [])
    emb_old = dados_revisao.get("embeddings_anteriores", [])
    chunks_novos = dados_revisao.get("chunks_novos", [])
    if chunks_novos:
        if not dados_revisao.get("embeddings_atualizados"):
            emb_new = [chunk.get("embedding") for chunk in chunks_novos if chunk.get("embedding")]
        else:
            emb_new = dados_revisao.get("embeddings_atualizados", [])
    else:
        emb_new = dados_revisao.get("embeddings_atualizados", [])

    metadados_globais = dados_revisao.get("metadados_associados", {})

    if not id_crenca:
        return {"erro": "ID da crenca nao fornecido"}

    fontes_removidas = [
        doc
        for doc in docs_fonte
        if doc.get("status") == "INVALIDO" or doc.get("http_status", 200) != 200
    ]

    if fontes_removidas:
        return {
            "id_crenca": id_crenca,
            "status_crenca": "OBSOLETA",
            "grau_mudanca": "alto",
            "documentos_afetados": [
                {"fonte": doc.get("url"), "tipo_mudanca": "remocao"} for doc in fontes_removidas
            ],
            "acao_recomendada": "SINALIZAR_OBSOLESCENCIA",
            "chunks_processados": [],
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": (
                f"Fontes originais inacessiveis: {[doc.get('url') for doc in fontes_removidas]}. "
                "Aguardando confirmacao do administrador."
            ),
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "AGENTE_CHROMADB",
        }

    if not emb_new:
        return {
            "id_crenca": id_crenca,
            "status_crenca": "INALTERADA",
            "grau_mudanca": "baixo",
            "documentos_afetados": [],
            "acao_recomendada": "MANTER",
            "chunks_processados": [],
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": (
                "Nao foram gerados novos embeddings para comparacao "
                "(possivel falha de processamento ou documento vazio). "
                "Mantendo estado atual por cautela."
            ),
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "NENHUM",
        }

    if len(emb_old) == 0:
        return {
            "id_crenca": id_crenca,
            "status_crenca": "ATUALIZADA",
            "grau_mudanca": "alto",
            "documentos_afetados": [],
            "acao_recomendada": "ATUALIZAR",
            "chunks_processados": chunks_novos,
            "metadados_associados": metadados_globais,
            "justificativa_tecnica": "Nao havia embeddings anteriores registrados. Atualizacao inicial.",
            "timestamp_revisao": datetime.now().isoformat(),
            "proximo_agente": "AGENTE_CHROMADB",
        }

    try:
        emb_old_np = np.array(emb_old, dtype=np.float32)
        emb_new_np = np.array(emb_new, dtype=np.float32)

        if ENV == "prod":
            sim_matrix = _calculate_cosine_similarity(emb_old_np, emb_new_np)
            max_similarities = sim_matrix.max(axis=1)
        else:
            try:
                from sentence_transformers import util
                sim_matrix = util.cos_sim(emb_old_np, emb_new_np)
                # O util.cos_sim retorna um tensor do PyTorch as vezes, ou numpy.
                # Para garantir compatibilidade com o codigo original:
                if hasattr(sim_matrix, "cpu"):
                    max_similarities = sim_matrix.max(axis=1).values.cpu().numpy()
                else:
                    max_similarities = sim_matrix.max(axis=1)
            except ImportError:
                # Fallback caso a lib nao esteja instalada mesmo em dev
                sim_matrix = _calculate_cosine_similarity(emb_old_np, emb_new_np)
                max_similarities = sim_matrix.max(axis=1)

        avg_similarity = float(max_similarities.mean())
        min_similarity = float(max_similarities.min())
    except Exception as e:
        return {"erro": f"Falha no calculo de similaridade: {str(e)}"}

    limiar_critico = 0.85
    limiar_alerta = 0.95

    status = "INALTERADA"
    grau = "baixo"
    acao = "MANTER"
    justificativa = f"Similaridade semantica media de {avg_similarity:.4f}."

    if avg_similarity < limiar_critico:
        status = "ATUALIZADA"
        grau = "alto"
        acao = "ATUALIZAR"
        justificativa = (
            "Detectada mudanca semantica relevante. "
            f"Similaridade media caiu para {avg_similarity:.4f} (minima: {min_similarity:.4f})."
        )
    elif avg_similarity < limiar_alerta:
        status = "ATUALIZADA"
        grau = "medio"
        acao = "ATUALIZAR"
        justificativa = f"Detectada mudanca semantica moderada. Similaridade media: {avg_similarity:.4f}."
    else:
        len_old = len(emb_old)
        len_new = len(emb_new)
        ratio = len_new / len_old if len_old > 0 else 0

        if ratio < 0.8 or ratio > 1.2:
            status = "ATUALIZADA"
            grau = "medio"
            acao = "ATUALIZAR"
            justificativa = (
                "Conteudo semantico similar, mas volume de informacao mudou "
                f"significativamente (Chunks: {len_old} -> {len_new})."
            )

    return {
        "id_crenca": id_crenca,
        "status_crenca": status,
        "grau_mudanca": grau,
        "documentos_afetados": [
            {"fonte": doc.get("url"), "tipo_mudanca": "conteudo"} for doc in docs_fonte
        ],
        "acao_recomendada": acao,
        "chunks_processados": chunks_novos if acao == "ATUALIZAR" else [],
        "metadados_associados": metadados_globais,
        "justificativa_tecnica": justificativa,
        "timestamp_revisao": datetime.now().isoformat(),
        "proximo_agente": "AGENTE_CHROMADB" if acao != "MANTER" else "NENHUM",
    }
