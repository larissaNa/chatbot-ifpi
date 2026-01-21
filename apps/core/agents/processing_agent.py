from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import uuid
import hashlib
from datetime import datetime
import re

# Inicializa o modelo de embedding globalmente
# Usando um modelo multilingue eficiente que funciona bem com português
try:
    embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
except Exception as e:
    print(f"Erro ao carregar modelo de embedding: {e}")
    embedding_model = None

def _generate_embedding(text: str) -> list:
    """Gera embedding para o texto usando sentence-transformers"""
    if not embedding_model:
        return []
    return embedding_model.encode(text).tolist()

def _calculate_hash(text: str) -> str:
    """Gera hash SHA-256 do conteúdo"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _split_semantic_chunks(text: str, chunk_size: int = 2000, chunk_overlap: int = 200) -> list:
    """
    Divide o texto em chunks semânticos respeitando estrutura normativa.
    chunk_size ~2000 caracteres aprox. 500 tokens (média 4 chars/token)
    """
    if not text:
        return []

    # Separadores hierárquicos para documentos legais/normativos
    separators = [
        "\n\nArt. ", "\n\nSeção ", "\n\nCapítulo ", "\n\nTÍTULO ", # Estruturas macro
        "\nArt. ", "\n§ ", "\nI - ", "\na) ",                      # Estruturas micro
        ". ", "; ", "\n", " "                                      # Fallback
    ]
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False
    )
    
    return splitter.split_text(text)

@tool
def processar_conteudo(extracao: dict) -> dict:
    """
    Processa texto extraído de documentos oficiais para indexação semântica.
    Realiza chunking, geração de embeddings e enriquecimento de metadados.
    
    Args:
        extracao (dict): Output do Agente de Extração contendo texto normalizado.
        
    Returns:
        dict: Dados processados com chunks, embeddings e metadados.
    """
    # Validação da entrada
    if not extracao or "documentos" not in extracao:
        return {
            "status": "erro",
            "mensagem": "Input inválido. Necessário output do Agente de Extração.",
            "proximo_agente": "NENHUM"
        }

    resultado_final = {
        "fonte": extracao.get("fonte", ""),
        "documento": "", # Será preenchido com o título do primeiro documento principal
        "chunks": [],
        "proximo_agente": "AGENTE_REVISAO_CRENCAS", # Próximo passo lógico na cadeia
        "status": "sucesso"
    }

    chunks_coletados = []
    
    documentos = extracao.get("documentos", [])
    if documentos:
        resultado_final["documento"] = documentos[0].get("titulo", "Documento Oficial")

    for doc in documentos:
        texto = doc.get("texto", doc.get("conteudo", ""))
        titulo = doc.get("titulo", "Sem título")
        tipo = doc.get("tipo", "desconhecido")
        metadata_original = doc.get("metadata", {})
        
        # 1. Chunking Semântico
        chunks_texto = _split_semantic_chunks(texto)
        
        for i, chunk_text in enumerate(chunks_texto):
            # 2. Geração de Embedding
            embedding = _generate_embedding(chunk_text)
            
            # 3. Metadados Ricos
            chunk_id = str(uuid.uuid4())
            content_hash = _calculate_hash(chunk_text)
            
            # Combina metadados originais com novos
            metadata_chunk = {
                "chunk_id": chunk_id,
                "fonte": extracao.get("fonte", ""),
                "documento_titulo": titulo,
                "documento_tipo": tipo,
                "secao_artigo": "n/a", # Implementação futura: extrair qual artigo o chunk pertence
                "ordem_no_documento": i,
                "total_chunks_doc": len(chunks_texto),
                "data_processamento": datetime.now().isoformat(),
                "hash_conteudo": content_hash,
                "tamanho_tokens_estimado": len(chunk_text) // 4
            }
            # Merge com metadata técnica da extração se existir
            metadata_chunk.update(metadata_original)

            chunks_coletados.append({
                "page_content": chunk_text,
                "metadata": metadata_chunk,
                "embedding": embedding
            })

    resultado_final["chunks"] = chunks_coletados
    resultado_final["total_chunks"] = len(chunks_coletados)
    
    return resultado_final
