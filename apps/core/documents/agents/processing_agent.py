import hashlib
import os
import uuid
from datetime import datetime

from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_huggingface import HuggingFaceEmbeddings

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _embedding_model


def _generate_embedding(text: str) -> list:
    """Gera embedding para o texto."""
    embedding_model = _get_embedding_model()
    return embedding_model.embed_query(text)


def _calculate_hash(text: str) -> str:
    """Gera hash SHA-256 do conteudo."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_semantic_chunks(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> list:
    """
    Divide o texto em chunks semanticos respeitando estrutura normativa.
    Aumentamos o overlap para 150 para garantir que o contexto de tabelas/listas não se perca entre chunks.
    """
    if not text:
        return []

    separators = [
        "\n\nArt. ",
        "\n\nSecao ",
        "\n\nCapitulo ",
        "\n\nTITULO ",
        "\nArt. ",
        "\n§ ",
        "\nI - ",
        "\na) ",
        ". ",
        "; ",
        "\n",
        " ",
    ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False,
    )

    return splitter.split_text(text)


@tool
def processar_conteudo(extracao: dict) -> dict:
    """
    Processa texto extraido de documentos oficiais para indexacao semantica.
    Realiza chunking, geracao de embeddings e enriquecimento de metadados.
    """
    if not extracao or "documentos" not in extracao:
        return {
            "status": "erro",
            "mensagem": "Input invalido. Necessario output do Agente de Extracao.",
            "proximo_agente": "NENHUM",
        }

    resultado_final = {
        "fonte": extracao.get("fonte", ""),
        "documento": "",
        "chunks": [],
        "proximo_agente": "AGENTE_REVISAO_CRENCAS",
        "status": "sucesso",
    }

    chunks_coletados = []

    documentos = extracao.get("documentos", [])
    if documentos:
        resultado_final["documento"] = documentos[0].get("titulo", "Documento Oficial")

    for doc in documentos:
        texto = doc.get("texto", doc.get("conteudo", ""))
        
        # Validação: Não gerar chunks se o conteúdo for inválido ou muito curto
        if not texto or len(texto.strip()) < 100:
            print(f"[PROCESSOR][WARN] Ignorando documento {doc.get('titulo')} devido a conteúdo insuficiente.")
            continue

        titulo = doc.get("titulo", "Sem titulo")
        tipo = doc.get("tipo", "desconhecido")
        metadata_original = doc.get("metadata", {})

        chunks_texto = _split_semantic_chunks(texto)

        for i, chunk_text in enumerate(chunks_texto):
            # page_content inclui o título como cabeçalho para que cada chunk
            # seja semanticamente autocontido — o embedding e o texto enviado
            # ao LLM usam o mesmo string, evitando divergência query/documento.
            has_title = titulo and titulo not in chunk_text
            page_content = f"[{titulo}]\n{chunk_text}" if has_title else chunk_text
            embedding = _generate_embedding(page_content)

            chunk_id = str(uuid.uuid4())
            content_hash = _calculate_hash(page_content)

            metadata_chunk = {
                "chunk_id": chunk_id,
                "fonte": extracao.get("fonte", ""),
                "documento_titulo": titulo,
                "documento_tipo": tipo,
                "secao_artigo": "n/a",
                "ordem_no_documento": i,
                "total_chunks_doc": len(chunks_texto),
                "data_processamento": datetime.now().isoformat(),
                "hash_conteudo": content_hash,
                "tamanho_tokens_estimado": len(page_content) // 4,
            }
            metadata_chunk.update(metadata_original)

            chunks_coletados.append(
                {
                    "page_content": page_content,
                    "metadata": metadata_chunk,
                    "embedding": embedding,
                }
            )

    resultado_final["chunks"] = chunks_coletados
    resultado_final["total_chunks"] = len(chunks_coletados)

    return resultado_final