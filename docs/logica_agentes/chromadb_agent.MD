# Agente ChromaDB – Implementação e Lógica

Este documento descreve o agente responsável pela **persistência vetorial** e execução das atualizações na memória institucional.

---

## 1. Onde está o Agente

* Arquivo: `apps/core/documents/agents/chromadb_agent.py`
* Tool LangChain: `executar_persistencia(dados_persistencia: dict)`
* Collection ChromaDB: `crencas_institucionais` (diretório `chroma_db/` na raiz do projeto)

---

## 2. Entrada esperada

Recebe diretamente o output do `belief_revision_agent`:

```json
{
  "id_crenca": "uuid-da-crenca",
  "acao_recomendada": "ATUALIZAR",
  "chunks_processados": [
    {
      "page_content": "Texto do chunk...",
      "embedding": [0.1, 0.2, ...],
      "metadata": {"pagina": 1}
    }
  ],
  "metadados_associados": {
    "titulo": "Resolução 001/2024",
    "fonte": "http://..."
  }
}
```

---

## 3. Ações Suportadas

| `acao_recomendada` | Comportamento |
|---|---|
| `MANTER` | Nenhuma operação no ChromaDB. |
| `SINALIZAR_OBSOLESCENCIA` | Não remove vetores. Marca `sugerido_obsoleto=True` no `DocumentoOficial` via SQL (quando em contexto Flask). Aguarda confirmação do administrador. |
| `REMOVER` | Remove todos os vetores com `id_crenca` da collection. |
| `ATUALIZAR` | (1) Remove vetores antigos com `id_crenca`. (2) Insere os novos chunks com IDs `{id_crenca}_{index}`. Requer lista de `chunks_processados` não vazia. |

### Sanitização de metadados

Antes de inserir no ChromaDB, o agente sanitiza os metadados de cada chunk:
- Valores `None` são convertidos para `""`
- Listas, dicts e outros tipos são convertidos para `str`
- Apenas `str`, `int`, `float` e `bool` passam sem conversão

### Contexto de banco SQL

O agente verifica `HAS_DB_CONTEXT` na inicialização. Se `apps.db` não estiver disponível (ex.: execução fora do Flask), as operações SQL de auditoria são puladas silenciosamente.

---

## 4. Saída do Agente (JSON)

```json
{
  "id_crenca": "uuid-da-crenca",
  "acao_executada": "ATUALIZAR",
  "resultado": {
    "chunks_inseridos": 15,
    "chunks_atualizados": 0,
    "chunks_removidos": 0
  },
  "status_banco": "CONSISTENTE",
  "observacoes": "Atualizacao completa. 15 chunks inseridos.",
  "timestamp_operacao": "2026-05-20T12:05:00"
}
```

Em caso de erro:
```json
{
  "id_crenca": "uuid-da-crenca",
  "acao_executada": "NENHUMA",
  "resultado": {"chunks_inseridos": 0, "chunks_atualizados": 0, "chunks_removidos": 0},
  "status_banco": "ALERTA",
  "observacoes": "Mensagem de erro...",
  "timestamp_operacao": "..."
}
```

---

## 5. Como testar

```python
from apps.core.documents.agents.chromadb_agent import executar_persistencia

resultado = executar_persistencia.invoke({
    "id_crenca": "meu-uuid",
    "acao_recomendada": "ATUALIZAR",
    "chunks_processados": [
        {"page_content": "Art. 1º ...", "embedding": [0.1, 0.2], "metadata": {}}
    ],
    "metadados_associados": {"titulo": "Resolução 001/2024"}
})
print(resultado)
```
