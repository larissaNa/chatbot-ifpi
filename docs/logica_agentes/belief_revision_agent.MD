# Agente de Revisão de Crenças – Implementação e Lógica

Este documento descreve o funcionamento do agente responsável pela **manutenção da memória institucional**.

---

## 1. Onde está o Agente

* Arquivo: `apps/core/documents/agents/belief_revision_agent.py`
* Tool LangChain: `revisar_crenca(dados_revisao: dict)`

---

## 2. Entrada esperada

```json
{
  "id_crenca": "uuid-da-crenca",
  "documentos_fonte": [
    {"url": "http://ifpi.edu.br/norma.pdf", "status": "OK", "http_status": 200}
  ],
  "embeddings_anteriores": [[0.1, 0.2, ...]],
  "chunks_novos": [
    {"page_content": "texto do chunk", "embedding": [0.1, 0.25, ...], "metadata": {}}
  ],
  "embeddings_atualizados": [[0.1, 0.25, ...]],
  "metadados_associados": {}
}
```

> `chunks_novos` tem prioridade para extrair os embeddings novos. Se não fornecido, usa `embeddings_atualizados`.

---

## 3. Lógica de Decisão

O agente compara vetores antigos e novos via **similaridade de cosseno**. Tenta usar `sentence_transformers.util.cos_sim`; se não estiver disponível, usa implementação numpy interna.

### Fluxo de decisão (em ordem de verificação)

| Condição | `status_crenca` | `acao_recomendada` | `proximo_agente` |
|---|---|---|---|
| `id_crenca` não fornecido | — | — | erro imediato |
| Alguma fonte com `status=INVALIDO` ou `http_status != 200` | `OBSOLETA` | `SINALIZAR_OBSOLESCENCIA` | `AGENTE_CHROMADB` |
| Nenhum embedding novo disponível | `INALTERADA` | `MANTER` | `NENHUM` |
| Sem embeddings anteriores (coleção vazia) | `ATUALIZADA` | `ATUALIZAR` | `AGENTE_CHROMADB` |
| Similaridade média < 0.85 | `ATUALIZADA` | `ATUALIZAR` | `AGENTE_CHROMADB` |
| Similaridade média < 0.95 | `ATUALIZADA` | `ATUALIZAR` | `AGENTE_CHROMADB` |
| Volume de chunks muda > 20% | `ATUALIZADA` | `ATUALIZAR` | `AGENTE_CHROMADB` |
| Similaridade >= 0.95 e volume estável | `INALTERADA` | `MANTER` | `NENHUM` |

> **Atenção:** A ação para fonte inválida mudou de `REMOVER` para `SINALIZAR_OBSOLESCENCIA`. A remoção efetiva fica a cargo de confirmação do administrador.

---

## 4. Saída do Agente (JSON)

```json
{
  "id_crenca": "uuid-da-crenca",
  "status_crenca": "ATUALIZADA",
  "grau_mudanca": "alto",
  "documentos_afetados": [
    {"fonte": "http://ifpi.edu.br/norma.pdf", "tipo_mudanca": "conteudo"}
  ],
  "acao_recomendada": "ATUALIZAR",
  "chunks_processados": [...],
  "metadados_associados": {},
  "justificativa_tecnica": "Detectada mudança semântica relevante. Similaridade media caiu para 0.76 (minima: 0.72).",
  "timestamp_revisao": "2026-05-20T12:00:00",
  "proximo_agente": "AGENTE_CHROMADB"
}
```

> `chunks_processados` é preenchido apenas quando `acao_recomendada == "ATUALIZAR"`.

---

## 5. Como testar

```python
from apps.core.documents.agents.belief_revision_agent import revisar_crenca

resultado = revisar_crenca.invoke({
    "id_crenca": "meu-uuid",
    "documentos_fonte": [{"url": "http://ifpi.edu.br/norma.pdf", "status": "OK", "http_status": 200}],
    "embeddings_anteriores": [],          # vazio = primeira indexação
    "chunks_novos": [
        {"page_content": "Art. 1º ...", "embedding": [0.1, 0.2], "metadata": {}}
    ]
})
print(resultado)
```
