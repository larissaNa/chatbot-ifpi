import os
from datetime import datetime

from apps import db
from apps.authentication import ChromaIndexRecord, DocumentoOficial, DocumentoVersao, LogProcessamento
from apps.core.documents.agents.belief_revision_agent import revisar_crenca
from apps.core.documents.agents.chromadb_agent import executar_persistencia
from apps.core.documents.agents.extraction_agent import extrair_conteudo
from apps.core.documents.agents.link_analysis_agent import analisar_link
from apps.core.documents.agents.processing_agent import processar_conteudo


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_chroma_collection():
    import chromadb
    ENV = os.getenv("ENV", "dev")

    if ENV == "prod":
        client = chromadb.EphemeralClient()
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base_dir, "..", "..", "..", ".."))
        persist_dir = os.path.join(project_root, "chroma_db")
        client = chromadb.PersistentClient(path=persist_dir)

    return client.get_or_create_collection(name="crencas_institucionais")


def log_to_terminal_and_db(msg, agente, acao, doc_id=None, versao_id=None):
    print(f"[LOG][{agente}][{acao}] {msg}")

    try:
        log = LogProcessamento(
            documento_id=doc_id,
            versao_id=versao_id,
            agente=agente,
            acao=acao,
            detalhe=msg,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Erro ao salvar log no banco: {e}")


def executar_revisao_documento(doc_id):
    doc = DocumentoOficial.query.get(doc_id)
    if not doc:
        return {"status": "erro", "mensagem": "Documento não encontrado"}

    log_to_terminal_and_db(f"Iniciando revisão para: {doc.titulo}", "ORCHESTRATOR", "START", doc_id=doc.id)

    log_to_terminal_and_db(f"Analisando link: {doc.url}", "LINK_ANALYZER", "START", doc_id=doc.id)
    try:
        resultado_analise = analisar_link.invoke({"url": doc.url})
        if resultado_analise.get("status") == "erro":
            msg = f"Erro na análise do link: {resultado_analise.get('mensagem')}"
            log_to_terminal_and_db(msg, "LINK_ANALYZER", "ERROR", doc_id=doc.id)
            return {"status": "erro", "mensagem": msg}
        log_to_terminal_and_db(
            f"Link analisado: {resultado_analise.get('tipo_conteudo')}",
            "LINK_ANALYZER",
            "SUCCESS",
            doc_id=doc.id,
        )
    except Exception as e:
        msg = f"Erro fatal no Agente de Análise: {str(e)}"
        log_to_terminal_and_db(msg, "LINK_ANALYZER", "ERROR", doc_id=doc.id)
        return {"status": "erro", "mensagem": msg}

    log_to_terminal_and_db("Iniciando extração de conteúdo...", "EXTRACTOR", "START", doc_id=doc.id)
    try:
        resultado_extracao = extrair_conteudo.invoke({"analise": resultado_analise})
        if resultado_extracao.get("status") == "erro":
            msg = f"Erro na extração: {resultado_extracao.get('mensagem')}"
            log_to_terminal_and_db(msg, "EXTRACTOR", "ERROR", doc_id=doc.id)
            return {"status": "erro", "mensagem": msg}
        log_to_terminal_and_db(
            f"Conteúdo extraído: {len(resultado_extracao.get('conteudo', ''))} caracteres",
            "EXTRACTOR",
            "SUCCESS",
            doc_id=doc.id,
        )
    except Exception as e:
        msg = f"Erro fatal no Agente de Extração: {str(e)}"
        log_to_terminal_and_db(msg, "EXTRACTOR", "ERROR", doc_id=doc.id)
        return {"status": "erro", "mensagem": msg}

    log_to_terminal_and_db("Iniciando processamento semântico...", "PROCESSOR", "START", doc_id=doc.id)
    try:
        resultado_processamento = processar_conteudo.invoke({"extracao": resultado_extracao})
    except Exception as e:
        msg = f"Erro fatal no Agente de Processamento: {str(e)}"
        log_to_terminal_and_db(msg, "PROCESSOR", "ERROR", doc_id=doc.id)
        return {"status": "erro", "mensagem": msg}

    if resultado_processamento.get("status") == "erro":
        log_to_terminal_and_db(resultado_processamento.get("mensagem"), "PROCESSOR", "ERROR", doc_id=doc.id)
        return resultado_processamento

    chunks_novos = resultado_processamento.get("chunks", [])
    embeddings_novos = [chunk.get("embedding") for chunk in chunks_novos]
    log_to_terminal_and_db(
        f"Processamento concluído. {len(chunks_novos)} chunks gerados.",
        "PROCESSOR",
        "SUCCESS",
        doc_id=doc.id,
    )

    id_crenca = f"doc_{doc.id}"
    collection = get_chroma_collection()
    try:
        old_data = collection.get(where={"id_crenca": id_crenca}, include=["embeddings", "metadatas"])
        embeddings_antigos = old_data.get("embeddings", []) if old_data else []
        log_to_terminal_and_db(
            f"Recuperados {len(embeddings_antigos)} embeddings antigos.",
            "RETRIEVER",
            "INFO",
            doc_id=doc.id,
        )
    except Exception as e:
        log_to_terminal_and_db(f"Erro ao buscar no Chroma: {e}", "RETRIEVER", "WARNING", doc_id=doc.id)
        embeddings_antigos = []

    dados_revisao = {
        "id_crenca": id_crenca,
        "texto_crenca": doc.titulo,
        "documentos_fonte": [{"url": doc.url, "status": "VALIDO", "http_status": 200}],
        "embeddings_anteriores": embeddings_antigos,
        "embeddings_atualizados": embeddings_novos,
        "chunks_novos": chunks_novos,
        "metadados_associados": {"fonte": doc.url, "doc_id": doc.id, "titulo": doc.titulo},
    }

    resultado_revisao = revisar_crenca.invoke({"dados_revisao": dados_revisao})

    if resultado_revisao.get("erro"):
        msg = f"Erro na revisão de crenças: {resultado_revisao.get('erro')}"
        log_to_terminal_and_db(msg, "BELIEF_REVISION", "ERROR", doc_id=doc.id)
        return {"status": "erro", "mensagem": msg}

    acao = resultado_revisao.get("acao_recomendada")
    justificativa = resultado_revisao.get("justificativa_tecnica")

    log_to_terminal_and_db(f"Decisão: {acao}. Motivo: {justificativa}", "BELIEF_REVISION", "DECISION", doc_id=doc.id)

    if acao in ["ATUALIZAR", "CRIAR"]:
        dados_persistencia = {
            "id_crenca": id_crenca,
            "acao_recomendada": "ATUALIZAR",
            "chunks_processados": chunks_novos,
            "metadados_associados": dados_revisao["metadados_associados"],
        }
        res_persistencia = executar_persistencia.invoke({"dados_persistencia": dados_persistencia})
        log_to_terminal_and_db(res_persistencia.get("observacoes", "Persistência concluída"), "CHROMADB", "SUCCESS", doc_id=doc.id)

        nova_versao_num = 1
        ultima_versao = (
            DocumentoVersao.query.filter_by(documento_id=doc.id)
            .order_by(DocumentoVersao.versao_numero.desc())
            .first()
        )
        if ultima_versao:
            nova_versao_num = ultima_versao.versao_numero + 1

        nova_versao = DocumentoVersao(
            documento_id=doc.id,
            versao_numero=nova_versao_num,
            url_arquivo=doc.url,
            hash_conteudo=chunks_novos[0]["metadata"].get("hash_conteudo") if chunks_novos else None,
            status_processamento="indexado",
            chroma_document_id=id_crenca,
            processado_em=datetime.now(),
            indexado_em=datetime.now(),
        )
        db.session.add(nova_versao)
        db.session.commit()

        doc.ultima_verificacao = datetime.now()
        db.session.commit()

        log_to_terminal_and_db(
            f"Nova versão {nova_versao_num} criada e registrada.",
            "SYSTEM",
            "VERSION_CONTROL",
            doc_id=doc.id,
            versao_id=nova_versao.id,
        )

    elif acao == "MANTER":
        doc.ultima_verificacao = datetime.now()
        db.session.commit()
        log_to_terminal_and_db("Documento inalterado. Nenhuma ação de escrita necessária.", "SYSTEM", "SKIP", doc_id=doc.id)

    elif acao == "SINALIZAR_OBSOLESCENCIA":
        doc.sugerido_obsoleto = True
        doc.ultima_verificacao = datetime.now()
        db.session.commit()
        log_to_terminal_and_db("Documento marcado como obsoleto.", "SYSTEM", "FLAG", doc_id=doc.id)

    return {"status": "sucesso", "acao": acao, "justificativa": justificativa}
