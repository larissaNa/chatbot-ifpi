# Agente de Processamento Semântico – Implementação e Integração

Este documento descreve:

* Onde o agente está no código
* Qual a entrada esperada (vinda do Agente de Extração)
* Como funciona o processamento semântico (Chunking e Embeddings)
* O formato exato do JSON de saída
* Como testar o agente na prática

---

## 1. Onde está o Agente de Processamento

### 1.1 Implementação principal

* Arquivo:
  `apps/core/agents/processing_agent.py`
* Tool LangChain:
  `processar_conteudo(extracao: dict)`

### 1.2 Integração como agente ReAct

* Arquivo:
  `apps/core/agents/react_agents.py`
* Agente criado:

  ```python
  processing_agent = create_react_agent(
      ...,
      tools=[processar_conteudo],
      prompt="Você é um Agente de Processamento Semântico...",
      name="processing_agent"
  )
  ```

O agente foi projetado para receber **diretamente o JSON produzido pelo Agente de Extração**, preparando os dados para a indexação vetorial.

---

## 2. Entrada esperada pelo Agente de Processamento

O tool `processar_conteudo` recebe um `dict` Python (ou JSON equivalente) contendo o texto normalizado e metadados básicos:

```json
{
  "fonte": "https://url-do-documento.pdf",
  "documentos": [
    {
      "titulo": "Resolução 01/2024",
      "tipo": "application/pdf",
      "conteudo": "Texto completo normalizado do documento...",
      "metadata": {
        "autor": "Conselho Superior",
        "data_extracao": "2024-03-20T10:00:00"
      }
    }
  ],
  "status": "sucesso"
}
```

📌 **Observação importante**
A entrada deve vir do output do `extraction_agent`. Se o status não for "sucesso" ou não houver documentos, o agente retornará erro.

---

## 3. Lógica de processamento implementada

Toda a lógica reside em funções auxiliares dentro de `apps/core/agents/processing_agent.py`.

### 3.1 Chunking Semântico

#### `_split_semantic_chunks(text: str)`

Utiliza o `RecursiveCharacterTextSplitter` do LangChain com separadores hierárquicos específicos para normas jurídicas e documentos institucionais:

1. **Macro-estruturas**: `\n\nArt. `, `\n\nSeção `, `\n\nCapítulo `
2. **Micro-estruturas**: `\nArt. `, `\n§ `, `\nI - `, `\na) `
3. **Fallback**: Quebras de linha, ponto final, espaços.

* **Tamanho do Chunk**: ~2000 caracteres (aprox. 500 tokens).
* **Overlap**: 200 caracteres para manter contexto nas bordas.

### 3.2 Geração de Embeddings

#### `_generate_embedding(text: str)`

* **Modelo**: `paraphrase-multilingual-MiniLM-L12-v2` (via `sentence-transformers`).
* **Característica**: Modelo leve e eficiente, otimizado para múltiplos idiomas incluindo Português.
* **Output**: Vetor denso (lista de floats).

### 3.3 Enriquecimento de Metadados

Cada chunk recebe metadados únicos para rastreabilidade:

* `chunk_id`: UUID único.
* `hash_conteudo`: Hash SHA-256 do texto do chunk (para detecção de duplicatas).
* `ordem_no_documento`: Posição sequencial do chunk.
* `tamanho_tokens_estimado`: Estimativa baseada em caracteres.

---

## 4. Saída do Agente (JSON para Indexação)

O agente retorna um JSON estruturado pronto para inserção no ChromaDB ou análise de crenças:

```json
{
  "fonte": "https://url-do-documento.pdf",
  "documento": "Resolução 01/2024",
  "status": "sucesso",
  "proximo_agente": "AGENTE_REVISAO_CRENCAS",
  "total_chunks": 15,
  "chunks": [
    {
      "page_content": "Art. 1º Fica estabelecido...",
      "embedding": [0.123, -0.456, ...],  // Vetor numérico
      "metadata": {
        "chunk_id": "uuid-v4...",
        "fonte": "https://url-do-documento.pdf",
        "documento_titulo": "Resolução 01/2024",
        "documento_tipo": "application/pdf",
        "ordem_no_documento": 0,
        "hash_conteudo": "sha256...",
        "data_processamento": "2024-03-20T10:05:00"
      }
    },
    // ... demais chunks
  ]
}
```

---

## 5. Como testar

Você pode testar o agente importando a ferramenta diretamente ou invocando o agente no grafo.

### Exemplo de teste unitário (Python)

```python
from apps.core.agents.processing_agent import processar_conteudo

mock_input = {
    "fonte": "http://teste.com",
    "documentos": [{
        "titulo": "Doc Teste",
        "conteudo": "Art. 1º Teste de processamento...", 
        "tipo": "text/plain"
    }]
}

resultado = processar_conteudo(mock_input)
print(f"Chunks gerados: {resultado['total_chunks']}")
print(f"Dimensão do embedding: {len(resultado['chunks'][0]['embedding'])}")
```
