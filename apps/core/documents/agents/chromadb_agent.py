import os
from datetime import datetime

from langchain_core.tools import tool

try:
    from apps import db
    from apps.authentication import ChromaIndexRecord, DocumentoOficial, DocumentoVersao

    HAS_DB_CONTEXT = True
except ImportError:
    HAS_DB_CONTEXT = False
    print("Warning: Running without SQL DB context. Audit logs will be skipped.")


def _project_root() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, "..", "..", "..", ".."))


@tool
def executar_persistencia(dados_persistencia: dict) -> dict:
    """
    Executa a persistencia de vetores no ChromaDB conforme decisao
    do Agente de Revisao.
    """
    id_crenca = dados_persistencia.get("id_crenca")
    acao = dados_persistencia.get("acao_recomendada")
    chunks = dados_persistencia.get("chunks_processados", [])
    metadados_globais = dados_persistencia.get("metadados_associados", {})

    if not id_crenca or not acao:
        return _erro_resposta(id_crenca, "Entrada invalida: id_crenca e acao_recomendada sao obrigatorios.")

    try:
        import chromadb

        persist_dir = os.path.join(_project_root(), "chroma_db")
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name="crencas_institucionais")
    except Exception as e:
        return _erro_resposta(id_crenca, f"Falha ao conectar ChromaDB: {str(e)}")

    inserted = 0
    updated = 0
    removed = 0
    status_db = "CONSISTENTE"
    obs = ""

    try:
        if acao == "MANTER":
            obs = "Nenhuma alteracao solicitada."

        elif acao == "SINALIZAR_OBSOLESCENCIA":
            obs = "Documento sinalizado como potencialmente obsoleto."

            if HAS_DB_CONTEXT:
                fonte_url = metadados_globais.get("fonte")
                if fonte_url:
                    _audit_sinalizar_obsolescencia_sql(fonte_url)
                else:
                    obs += " (URL da fonte nao encontrada nos metadados para atualizacao SQL)"

        elif acao == "REMOVER":
            collection.delete(where={"id_crenca": id_crenca})
            removed = 1
            obs = "Remocao executada."

            if HAS_DB_CONTEXT:
                _audit_remover_sql(id_crenca)

        elif acao == "ATUALIZAR":
            if not chunks:
                return _erro_resposta(id_crenca, "Acao ATUALIZAR requer lista de chunks.")

            collection.delete(where={"id_crenca": id_crenca})

            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{id_crenca}_{i}"
                ids.append(chunk_id)
                documents.append(chunk.get("page_content", ""))
                embeddings.append(chunk.get("embedding"))

                meta = chunk.get("metadata", {}).copy()
                meta.update(metadados_globais)
                meta["id_crenca"] = id_crenca
                meta["timestamp"] = datetime.now().isoformat()

                sanitized_meta = {}
                for key, value in meta.items():
                    if value is None:
                        sanitized_meta[key] = ""
                    elif isinstance(value, (str, int, float, bool)):
                        sanitized_meta[key] = value
                    else:
                        sanitized_meta[key] = str(value)

                metadatas.append(sanitized_meta)

            if ids:
                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
                inserted = len(ids)
                obs = f"Atualizacao completa. {inserted} chunks inseridos."

                if HAS_DB_CONTEXT:
                    _audit_atualizar_sql(id_crenca, ids)

    except Exception as e:
        status_db = "ALERTA"
        obs = f"Erro durante operacao ChromaDB: {str(e)}"
        return _erro_resposta(id_crenca, obs, status_db)

    return {
        "id_crenca": id_crenca,
        "acao_executada": acao,
        "resultado": {
            "chunks_inseridos": inserted,
            "chunks_atualizados": updated,
            "chunks_removidos": removed,
        },
        "status_banco": status_db,
        "observacoes": obs,
        "timestamp_operacao": datetime.now().isoformat(),
    }


def _erro_resposta(id_crenca, msg, status="ALERTA"):
    return {
        "id_crenca": id_crenca or "unknown",
        "acao_executada": "NENHUMA",
        "resultado": {
            "chunks_inseridos": 0,
            "chunks_atualizados": 0,
            "chunks_removidos": 0,
        },
        "status_banco": status,
        "observacoes": msg,
        "timestamp_operacao": datetime.now().isoformat(),
    }


def _audit_remover_sql(id_crenca):
    try:
        pass
    except Exception:
        pass


def _audit_atualizar_sql(id_crenca, chunk_ids):
    try:
        pass
    except Exception:
        pass


def _audit_sinalizar_obsolescencia_sql(url):
    try:
        doc = DocumentoOficial.query.filter_by(url=url).first()
        if doc:
            doc.sugerido_obsoleto = True
            db.session.commit()
            print(f"[AUDIT] Documento {doc.titulo} sinalizado como obsoleto.")
    except Exception as e:
        print(f"[AUDIT] Erro ao sinalizar obsolescencia: {e}")
