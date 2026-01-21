# Agente ChromaDB – Implementação e Lógica

Este documento descreve o funcionamento do agente responsável pela **persistência vetorial** e execução final das atualizações na memória institucional.

---

## 1. Onde está o Agente ChromaDB

### 1.1 Implementação principal

* Arquivo:
  [`apps/core/agents/chromadb_agent.py`](file:///c:/Users/Larisssa/Projetos/projeto de pesquisa/chatbot-ifpi/apps/core/agents/chromadb_agent.py)
* Tool LangChain:
  `executar_persistencia(dados_persistencia: dict)`

### 1.2 Integração no Pipeline

Este agente atua como o **executor final** (sink) do pipeline de revisão de crenças. Ele recebe as ordens do Agente de Revisão e aplica as mudanças no banco de dados vetorial.

---

## 2. Entrada esperada

O tool `executar_persistencia` espera um dicionário contendo a decisão de revisão e os dados necessários para persistência (provenientes do output do `belief_revision_agent`):

```json
{
  "id_crenca": "uuid-da-crenca",
  "acao_recomendada": "ATUALIZAR", // Opções: MANTER | ATUALIZAR | REMOVER
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

## 3. Lógica de Execução

O agente opera de forma determinística baseada na `acao_recomendada`.

### Ações Suportadas

1.  **MANTER**:
    *   **Comportamento**: Nenhuma operação de escrita é realizada no banco.
    *   **Log**: Registra que a crença foi verificada e mantida.

2.  **REMOVER**:
    *   **Comportamento**: Remove todos os vetores associados ao `id_crenca` na collection do ChromaDB.
    *   **Contexto**: Utilizado quando a fonte original se torna inválida ou inacessível.

3.  **ATUALIZAR**:
    *   **Passo 1 (Limpeza)**: Remove preventivamente todos os vetores antigos associados ao `id_crenca` para evitar duplicatas ou chunks "órfãos".
    *   **Passo 2 (Preparação)**: Gera IDs únicos para os novos chunks (`{id_crenca}_{index}`) e mescla os metadados do chunk com os metadados globais.
    *   **Passo 3 (Inserção)**: Insere os novos vetores e documentos na collection.

### Persistência

*   Utiliza o diretório local `chroma_db` (na raiz do projeto) para armazenar os dados de forma persistente.
*   Cria/Usa a collection `crencas_institucionais`.

---

## 4. Saída do Agente (JSON)

O retorno confirma a execução da operação e fornece estatísticas para auditoria:

```json
{
  "id_crenca": "uuid-da-crenca",
  "acao_executada": "ATUALIZAR",
  "resultado": {
    "chunks_inseridos": 15,
    "chunks_atualizados": 0,
    "chunks_removidos": 0
  },
  "status_banco": "CONSISTENTE", // ou ALERTA em caso de erro
  "observacoes": "Atualização completa. 15 chunks inseridos.",
  "timestamp_operacao": "2024-03-20T12:05:00"
}
```

---

## 5. Como testar

Utilize o script de teste criado em `tests/test_chromadb_agent.py`. Este teste utiliza **mocks** para simular o ChromaDB, garantindo que o teste não escreva no banco real e seja rápido.

```bash
python tests/test_chromadb_agent.py
```

Isso valida os três fluxos principais (`MANTER`, `REMOVER`, `ATUALIZAR`) e a integridade da passagem de parâmetros.
