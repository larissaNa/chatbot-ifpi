from langchain_core.tools import tool
from datetime import datetime
import json
import os
import chromadb
from chromadb.config import Settings

# Import db and models if available, otherwise use placeholders/mocks
try:
    from apps import db
    from apps.authentication.models import ChromaIndexRecord, DocumentoVersao, DocumentoOficial
    HAS_DB_CONTEXT = True
except ImportError:
    HAS_DB_CONTEXT = False
    print("Warning: Running without SQL DB context. Audit logs will be skipped.")

@tool
def executar_persistencia(dados_persistencia: dict) -> dict:
    """
    Executa a persistência de vetores no ChromaDB conforme decisão do Agente de Revisão.
    
    Args:
        dados_persistencia (dict): Dicionário contendo:
            - id_crenca (str): ID do documento/crença.
            - acao_recomendada (str): MANTER | ATUALIZAR | REMOVER.
            - chunks_processados (list): Lista de chunks com 'page_content', 'metadata' e 'embedding'.
            - metadados_associados (dict): Metadados globais.
            
    Returns:
        dict: Resultado da operação no formato padronizado.
    """
    
    # 1. Extração e Validação
    id_crenca = dados_persistencia.get("id_crenca")
    acao = dados_persistencia.get("acao_recomendada")
    chunks = dados_persistencia.get("chunks_processados", [])
    metadados_globais = dados_persistencia.get("metadados_associados", {})
    
    if not id_crenca or not acao:
        return _erro_resposta(id_crenca, "Entrada inválida: id_crenca e acao_recomendada são obrigatórios.")

    # Setup ChromaDB
    try:
        # Define o diretório de persistência na raiz do projeto
        # apps/core/agents/chromadb_agent.py -> ../../../ -> root
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
        persist_dir = os.path.join(project_root, "chroma_db")
        
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
            obs = "Nenhuma alteração solicitada."
            
        elif acao == "SINALIZAR_OBSOLESCENCIA":
            # Não remove vetores, apenas marca no banco SQL para revisão humana
            obs = "Documento sinalizado como potencialmente obsoleto."
            
            if HAS_DB_CONTEXT:
                # Tenta obter a URL dos metadados para localizar o documento
                fonte_url = metadados_globais.get("fonte")
                if fonte_url:
                    _audit_sinalizar_obsolescencia_sql(fonte_url)
                else:
                    obs += " (URL da fonte não encontrada nos metadados para atualização SQL)"

        elif acao == "REMOVER":
            # Remove todos os chunks associados a este id_crenca
            # Assumindo que id_crenca está nos metadados como filtro
            collection.delete(where={"id_crenca": id_crenca})
            removed = 1 # Representa a remoção do documento lógico, não contagem exata de chunks se não consultarmos antes
            obs = "Remoção executada."
            
            # Audit SQL
            if HAS_DB_CONTEXT:
                _audit_remover_sql(id_crenca)

        elif acao == "ATUALIZAR":
            if not chunks:
                return _erro_resposta(id_crenca, "Ação ATUALIZAR requer lista de chunks.")
            
            # 1. Remove versão anterior para garantir limpeza (clean slate para o documento)
            collection.delete(where={"id_crenca": id_crenca})
            
            # 2. Prepara novos dados
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{id_crenca}_{i}" # ID único para o chunk no Chroma
                ids.append(chunk_id)
                documents.append(chunk.get("page_content", ""))
                embeddings.append(chunk.get("embedding"))
                
                # Merge metadata
                meta = chunk.get("metadata", {}).copy()
                meta.update(metadados_globais)
                meta["id_crenca"] = id_crenca # Chave de ligação
                meta["timestamp"] = datetime.now().isoformat()
                
                # Sanitize metadata (ChromaDB does not allow None values)
                sanitized_meta = {}
                for k, v in meta.items():
                    if v is None:
                        sanitized_meta[k] = "" # Replace None with empty string
                    elif isinstance(v, (str, int, float, bool)):
                        sanitized_meta[k] = v
                    else:
                        sanitized_meta[k] = str(v) # Convert other types to string
                
                metadatas.append(sanitized_meta)
            
            # 3. Insere
            if ids:
                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
                inserted = len(ids)
                obs = f"Atualização completa. {inserted} chunks inseridos."
                
                # Audit SQL
                if HAS_DB_CONTEXT:
                    _audit_atualizar_sql(id_crenca, ids)

    except Exception as e:
        status_db = "ALERTA"
        obs = f"Erro durante operação ChromaDB: {str(e)}"
        return _erro_resposta(id_crenca, obs, status_db)

    # Output Final
    return {
        "id_crenca": id_crenca,
        "acao_executada": acao,
        "resultado": {
            "chunks_inseridos": inserted,
            "chunks_atualizados": updated, # Chroma 'upsert' or delete+insert counts as insert usually, but logic here is insert
            "chunks_removidos": removed
        },
        "status_banco": status_db,
        "observacoes": obs,
        "timestamp_operacao": datetime.now().isoformat()
    }

def _erro_resposta(id_crenca, msg, status="ALERTA"):
    return {
        "id_crenca": id_crenca or "unknown",
        "acao_executada": "NENHUMA",
        "resultado": {"chunks_inseridos": 0, "chunks_atualizados": 0, "chunks_removidos": 0},
        "status_banco": status,
        "observacoes": msg,
        "timestamp_operacao": datetime.now().isoformat()
    }

def _audit_remover_sql(id_crenca):
    try:
        # Tenta encontrar registros ativos e desativar
        # Nota: id_crenca deve corresponder a algo rastreável.
        # Aqui assumimos que id_crenca pode ser mapeado para chroma_document_id ou similar
        # Como é um exemplo, faremos um update genérico se possível
        # db.session.query(ChromaIndexRecord).filter...
        pass 
    except Exception:
        pass

def _audit_atualizar_sql(id_crenca, chunk_ids):
    try:
        # Registrar novos chunks no SQL
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
        print(f"[AUDIT] Erro ao sinalizar obsolescência: {e}")
