# Agente de Revisão de Crenças – Implementação e Lógica

Este documento descreve o funcionamento do agente responsável pela **manutenção da memória institucional**.

---

## 1. Onde está o Agente de Revisão

### 1.1 Implementação principal

* Arquivo:
  `apps/core/agents/belief_revision_agent.py`
* Tool LangChain:
  `revisar_crenca(dados_revisao: dict)`

### 1.2 Integração como agente ReAct

* Arquivo:
  `apps/core/agents/react_agents.py`
* Agente criado:
  `belief_revision_agent`

Este agente atua no final do pipeline, decidindo o destino de uma crença baseada na comparação entre o estado antigo e o novo processamento.

---

## 2. Entrada esperada

O tool `revisar_crenca` espera um dicionário contendo o histórico e os novos dados:

```json
{
  "id_crenca": "uuid-da-crenca",
  "texto_crenca": "O prazo para rematrícula é de 5 dias.",
  "documentos_fonte": [
    {"url": "http://ifpi.edu.br/norma.pdf", "status": "OK"}
  ],
  "embeddings_anteriores": [[0.1, 0.2, ...], ...],  // Lista de vetores da versão anterior
  "embeddings_atualizados": [[0.1, 0.25, ...], ...] // Lista de vetores da nova versão (output do Processing Agent)
}
```

---

## 3. Lógica de Decisão

O agente não gera embeddings. Ele utiliza **comparação de similaridade de cosseno** (via `sentence-transformers`) entre os vetores antigos e novos.

### Critérios de Classificação

1.  **Integridade da Fonte**:
    *   Se `status` da fonte for `INVALIDO` ou HTTP != 200 → **OBSOLETA**.
    *   Ação: `REMOVER`.

2.  **Similaridade Semântica**:
    *   Calcula-se a similaridade média entre os chunks antigos e os novos mais próximos.
    *   **Similaridade < 0.85** (Limiar Crítico) → **ATUALIZADA** (Mudança Relevante).
    *   **Similaridade < 0.95** (Limiar Alerta) → **ATUALIZADA** (Mudança Moderada).
    *   **Similaridade >= 0.95** → **INALTERADA**.

3.  **Volume de Informação**:
    *   Se a quantidade de chunks mudar drasticamente (>20%), também sinaliza **ATUALIZADA**.

---

## 4. Saída do Agente (JSON)

O formato de resposta é estrito para permitir automação pelo orquestrador:

```json
{
  "id_crenca": "uuid-da-crenca",
  "status_crenca": "ATUALIZADA",
  "grau_mudanca": "alto",
  "documentos_afetados": [
    {
      "fonte": "http://ifpi.edu.br/norma.pdf",
      "tipo_mudanca": "conteudo"
    }
  ],
  "acao_recomendada": "ATUALIZAR",
  "justificativa_tecnica": "Detectada mudança semântica relevante. Similaridade média caiu para 0.76.",
  "timestamp_revisao": "2024-03-20T12:00:00",
  "proximo_agente": "AGENTE_CHROMADB"
}
```

---

## 5. Como testar

Utilize o script de teste criado em `tests/test_belief_revision.py`:

```bash
python tests/test_belief_revision.py
```

Isso simula três cenários:
1.  **Manutenção**: Embeddings idênticos.
2.  **Atualização**: Embeddings diferentes (simulados com vetores aleatórios).
3.  **Obsolescência**: Fonte removida/inválida.
