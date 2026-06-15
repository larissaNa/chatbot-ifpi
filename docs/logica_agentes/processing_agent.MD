# Agente de Processamento Semântico – Implementação e Integração

Este documento descreve o agente responsável por transformar texto extraído em chunks vetorizados prontos para indexação.

---

## 1. Onde está o Agente

* Arquivo: `apps/core/documents/agents/processing_agent.py`
* Tool LangChain: `processar_conteudo(extracao: dict)`

---

## 2. Entrada esperada

Recebe diretamente o output do `extraction_agent` (status `"sucesso"`):

```json
{
  "fonte": "https://url-do-documento.pdf",
  "documentos": [
    {
      "titulo": "Resolução 01/2024",
      "texto": "Texto completo normalizado do documento...",
      "metadata": {
        "paginas_estimadas": 5,
        "idioma": "pt",
        "tipo_extracao": "PDF_TEXTUAL"
      }
    }
  ]
}
```

Documentos com texto menor que 100 caracteres são ignorados com aviso de log.

---

## 3. Lógica de processamento

### 3.1 Chunking Semântico

Função: `_split_semantic_chunks(text, chunk_size=800, chunk_overlap=150)`

Usa `RecursiveCharacterTextSplitter` com separadores hierárquicos:

1. `\n\nArt. `, `\n\nSecao `, `\n\nCapitulo `, `\n\nTITULO `
2. `\nArt. `, `\n§ `, `\nI - `, `\na) `
3. `. `, `; `, `\n`, ` `

> **chunk_size foi reduzido para 800** (era 2000) e **overlap para 150** (era 200), para granularidade maior e melhor precisão no RAG. O overlap maior (150) garante que o contexto de tabelas e listas não se perca na fronteira entre chunks.

### 3.2 `page_content` com cabeçalho de título

Cada chunk inclui o título do documento como cabeçalho, se ele ainda não estiver no texto:

```
[Resolução 01/2024]
Art. 1º Fica estabelecido...
```

Isso garante que o embedding e o texto enviado ao LLM usem o mesmo string, **evitando divergência query/documento**.

### 3.3 Geração de Embeddings

Função: `_generate_embedding(text)`

* Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via `HuggingFaceEmbeddings`
* **`normalize_embeddings=True` é obrigatório.** Sem normalização, os vetores têm norma L2 ~10-14, tornando a distância L2 dominada pela magnitude e não pela direção semântica — todos os scores ficam igualmente baixos.
* Modelo carregado com lazy loading (`_get_embedding_model()`): instanciado uma única vez e reutilizado.

### 3.4 Metadados de cada chunk

```python
{
    "chunk_id": "uuid-v4",
    "fonte": "https://...",
    "documento_titulo": "Resolução 01/2024",
    "documento_tipo": "desconhecido",
    "secao_artigo": "n/a",
    "ordem_no_documento": 0,
    "total_chunks_doc": 12,
    "data_processamento": "2026-05-20T10:05:00",
    "hash_conteudo": "sha256...",
    "tamanho_tokens_estimado": 200,
    # + campos do metadata original do documento (paginas_estimadas, idioma, etc.)
}
```

---

## 4. Saída do Agente (JSON)

```json
{
  "fonte": "https://url-do-documento.pdf",
  "documento": "Resolução 01/2024",
  "status": "sucesso",
  "proximo_agente": "AGENTE_REVISAO_CRENCAS",
  "total_chunks": 12,
  "chunks": [
    {
      "page_content": "[Resolução 01/2024]\nArt. 1º Fica estabelecido...",
      "embedding": [0.123, -0.456, ...],
      "metadata": { "chunk_id": "...", "ordem_no_documento": 0, ... }
    }
  ]
}
```

---

## 5. Como testar

```python
from apps.core.documents.agents.processing_agent import processar_conteudo

resultado = processar_conteudo.invoke({
    "fonte": "http://teste.com",
    "documentos": [{
        "titulo": "Resolução 001/2024",
        "texto": "Art. 1º Fica estabelecido que todos os alunos devem...",
        "metadata": {"paginas_estimadas": 1, "idioma": "pt", "tipo_extracao": "PDF_TEXTUAL"}
    }]
})

print(f"Chunks gerados: {resultado['total_chunks']}")
print(f"Dimensão do embedding: {len(resultado['chunks'][0]['embedding'])}")
```
