# Agente de Análise de Links – Implementação

Este documento descreve:

* Onde o código foi implementado
* O comportamento detalhado do agente
* A lógica de decisão do tipo de conteúdo
* O formato de saída (JSON)
* Exemplos reais de retorno
* Como utilizar o agente atualmente

---

## 1. Onde o agente foi criado

### 1.1 Função principal de análise (sem LLM)

* Arquivo:
  `apps/core/agents/search_agent.py`
* Função interna:
  `_analise_basica_url(url: str) -> dict`
* Tool LangChain (Agente de Análise de Links):
  `analisar_link(url: str) -> dict`

### 1.2 Agente ReAct dedicado à análise de links

* Arquivo:
  `apps/core/agents/react_agents.py`
* Objeto criado:

  ```python
  link_analysis_agent = create_react_agent(..., tools=[analisar_link], ...)
  ```

### 1.3 Model de link já existente

* Arquivo:
  `apps/authentication/models.py – DocumentoOficial`
* Observação:
  São utilizados os campos:

  * `ultima_verificacao`
  * `ultimo_status_http`

Esses campos registram o resultado básico da validação HTTP.

---

## 2. Comportamento do agente de análise

A lógica central está na função `_analise_basica_url`, exposta como ferramenta LangChain através de `analisar_link`.

### 2.1 Validação da URL

* Remove espaços em branco
* Verifica:

  * URL vazia
    → `status="ERRO"`
    → `tipo_conteudo="INVALIDO"`
  * Esquema diferente de `http` ou `https`, ou ausência de `netloc`
    → `status="ERRO"`
    → `tipo_conteudo="INVALIDO"`
* Validação realizada com `urlparse`

---

### 2.2 Validação de acessibilidade (HTTP)

* Executa:

  ```python
  requests.head(url, allow_redirects=True, timeout=10)
  ```
* Captura:

  * `status_code`
  * `Content-Type` (antes do `;`) → `mime_type`

#### Atualização no banco (se URL já cadastrada)

* Busca `DocumentoOficial` pelo campo `url`
* Atualiza:

  * `ultima_verificacao = datetime.utcnow()`
  * `ultimo_status_http = status_code`
* Executa `db.session.commit()`

#### Status HTTP diferente de 200

* Resultado:

  * `status="ERRO"`
  * `tipo_conteudo="INVALIDO"`
  * `observacoes="URL inacessível (status HTTP XXX)."`
  * `proximo_agente="NENHUM"`

---

### 2.3 Detecção de PDF direto (`PDF_DIRETO`)

#### Condição

* `mime_type == "application/pdf"` **ou**
* Caminho da URL termina com `.pdf` (case-insensitive)

#### Resultado

* `status="SUCESSO"`
* `tipo_conteudo="PDF_DIRETO"`
* `proximo_agente="AGENTE_EXTRACAO"`

#### Observações adicionais

* O PDF **não é baixado**

* Não há OCR nem embeddings

* Busca indícios de documento oficial **apenas na URL**, em minúsculas:

  * `ifpi`
  * `instituto federal do piauí`
  * `resolucao / resolução`
  * `portaria`
  * `norma`
  * `edital`

* Se encontrados:

  ```
  Indícios de documento oficial na URL: ...
  ```

* Caso contrário:

  ```
  Link PDF direto; análise de conteúdo delegada ao próximo agente.
  ```

---

### 2.4 Tipos de conteúdo não suportados

* Se `mime_type` existir e:

  * Não contiver `"html"`
  * Não for classificado como PDF

Resultado:

* `status="ERRO"`
* `tipo_conteudo="INVALIDO"`
* `observacoes="Tipo de conteúdo não suportado: <mime>."`
* `proximo_agente="NENHUM"`

---

### 2.5 Página HTML (`text/html`)

* Executa:

  ```python
  requests.get(url, timeout=15)
  ```
* Apenas para HTML (PDFs não são baixados)

#### GET diferente de 200

* `status="ERRO"`
* `tipo_conteudo="INVALIDO"`
* `proximo_agente="NENHUM"`

---

### 2.6 Análise superficial do HTML

Usando `BeautifulSoup`:

#### Extração de título

* `soup.find("title")`
* Se existir e não estiver vazio → `titulo`

#### Detecção de PDFs na página

* Varre todas as tags `<a>` com `href`
* Se `href` terminar com `.pdf`:

  * URL absoluta:

    * Se começar com `http`, usa direto
    * Caso contrário, usa `urljoin`
* Estrutura:

  ```json
  {
    "url": "<link do pdf>",
    "descricao": "<texto do link ou vazio>"
  }
  ```

#### Texto para palavras-chave

* Concatena:

  * `titulo`
  * Texto da página (limitado a 5000 caracteres)
* Converte para minúsculas
* Busca termos:

  * `ifpi`
  * `instituto federal do piauí`
  * `resolucao / resolução`
  * `portaria`
  * `norma`
  * `instrucao normativa / instrução normativa`
  * `edital`
  * `comunicado`

---

### 2.7 Classificação final do tipo de conteúdo

#### Caso existam PDFs na página

* `tipo_conteudo="HTML_COM_PDF"`
* `status="SUCESSO"`
* `proximo_agente="AGENTE_EXTRACAO"`
* `observacoes`:

  * `<N> PDF(s) encontrado(s) na página.`
  * Indícios institucionais (se encontrados)

---

#### Caso não existam PDFs

* Calcula:

  ```python
  len(soup.get_text(strip=True))
  ```

##### Texto ≥ 300 caracteres

* `tipo_conteudo="HTML_TEXTO"`
* `status="SUCESSO"`
* `proximo_agente="AGENTE_EXTRACAO"`
* `observacoes`:

  * Indícios institucionais (se houver)
  * Ou:

    ```
    Página HTML analisada sem indícios fortes de documento oficial.
    ```

##### Texto < 300 caracteres

* `tipo_conteudo="INVALIDO"`
* `status="SUCESSO"`
* `proximo_agente="NENHUM"`
* `observacoes`:

  ```
  Conteúdo aparentemente irrelevante ou muito curto.
  ```

---

### 2.8 Erros de rede ou exceções

* Timeouts, DNS, falhas de conexão (HEAD ou GET):

  * `status="ERRO"`
  * `tipo_conteudo="INVALIDO"`
  * `proximo_agente="NENHUM"`
  * `observacoes` com a mensagem técnica do erro

---

## 3. Formato de saída (JSON)

A função `_analise_basica_url` e a tool `analisar_link` retornam **sempre** um `dict` serializável em JSON:

```python
{
  "url": "<link analisado>",
  "status": "SUCESSO" | "ERRO",
  "tipo_conteudo": "PDF_DIRETO" | "HTML_COM_PDF" | "HTML_TEXTO" | "INVALIDO",
  "titulo": "<titulo detectado ou None>",
  "mime_type": "<mime type ou None>",
  "pdfs_encontrados": [
    {
      "url": "<link do pdf>",
      "descricao": "<texto âncora ou contexto>"
    }
  ],
  "observacoes": "<observações relevantes>",
  "proximo_agente": "AGENTE_EXTRACAO" | "NENHUM"
}
```

---

## 4. Como usar o agente hoje

### Uso direto no Python

```python
from apps.core.agents.search_agent import analisar_link

resultado = analisar_link.invoke({"url": "https://seu-link-aqui"})

import json
print(json.dumps(resultado, ensure_ascii=False, indent=2))
```

### Uso via agente ReAct (LangChain/LangGraph)

```python
from apps.core.agents.react_agents import link_analysis_agent

res = link_analysis_agent.invoke("Analise o link https://seu-link-aqui")
```

> O modelo deve ser instruído a sempre chamar a ferramenta `analisar_link` e retornar **apenas o JSON** produzido por ela.

---

## 5. Garantias em relação às regras definidas

✔ Não faz OCR
✔ Não cria embeddings
✔ Não acessa ChromaDB
✔ Não interpreta conteúdo normativo

O agente apenas:

* Valida URL e status HTTP
* Classifica o tipo de conteúdo
* Extrai metadados básicos
* Detecta sinais institucionais
* Define o próximo agente (`AGENTE_EXTRACAO` ou `NENHUM`)

--

# Testes do Agente de Análise de Links

A seguir são apresentadas **três formas de testar o Agente de Análise de Links**, indo da mais simples (função Python pura) até o uso completo como **tool/agent integrado ao LangGraph/LangChain**.

---

## 1. Teste rápido da lógica (sem LangChain)

Este é o método **mais simples e confiável**, pois testa apenas a **função pura**, sem interferência de LLM ou fluxo de agentes.

### 1.1 Acessar o container da aplicação

```bash
docker-compose exec appseed_app bash
```

### 1.2 Executar o teste no Python REPL

```python
from apps.core.agents.search_agent import _analise_basica_url
import json

url = "https://www.ifpi.edu.br/algum-doc.pdf"
res = _analise_basica_url(url)

print(json.dumps(res, ensure_ascii=False, indent=2))
```

### 1.3 Exemplo de saída esperada

```json
{
  "url": "https://www.ifpi.edu.br/algum-doc.pdf",
  "status": "SUCESSO",
  "tipo_conteudo": "PDF_DIRETO",
  "titulo": null,
  "mime_type": "application/pdf",
  "pdfs_encontrados": [],
  "observacoes": "Indícios de documento oficial na URL: ifpi, resolucao",
  "proximo_agente": "AGENTE_EXTRACAO"
}
```

### 1.4 Casos recomendados para teste

Utilize URLs diferentes para validar o comportamento:

* PDF direto (`.../arquivo.pdf`)
* Página HTML com múltiplos PDFs
* Página HTML apenas com texto
* URL inexistente ou inválida

Verifique se os campos `tipo_conteudo` e `proximo_agente` correspondem ao esperado em cada caso.

---

## 2. Teste do tool `analisar_link` (LangChain Tool)

Este teste valida o agente **da forma como o LangChain o enxerga**, usando o tool decorado com `@tool`.

### 2.1 Execução via `.invoke()` (forma recomendada)

```python
from apps.core.agents.search_agent import analisar_link
import json

res = analisar_link.invoke({"url": "https://www.ifpi.edu.br/algum-doc.pdf"})
print(json.dumps(res, ensure_ascii=False, indent=2))
```

### 2.2 Observações importantes

* `analisar_link` é um **tool LangChain**, portanto:

  * Pode ser chamado diretamente como função:

    ```python
    res = analisar_link.func("https://www.ifpi.edu.br/algum-doc.pdf")
    ```
  * Porém, para simular corretamente o uso em grafos e agentes, **prefira**:

    ```python
    analisar_link.invoke({"url": ...})
    ```

Se este teste retornar corretamente o JSON no formato esperado, o **Agente de Análise de Links está funcional** no contexto do LangChain.

---

## 3. Teste do agente ReAct `link_analysis_agent`

Este teste valida o fluxo **completo**, envolvendo:

* LLM
* Prompt
* Tool `analisar_link`
* Retorno estruturado

### 3.1 Definição do agente

No arquivo `react_agents.py`, o agente foi definido como:

```python
link_analysis_agent = create_react_agent(
    model=llm,
    tools=[analisar_link],
    prompt=(
        "Você é um Agente de Análise de Links institucionais. "
        "Ao receber uma URL, valide, classifique e retorne exclusivamente um JSON "
        "no formato especificado pela arquitetura de Revisão de Crenças."
    ),
    name="link_analysis_agent"
)
```

### 3.2 Execução do agente

```python
from apps.core.agents.react_agents import link_analysis_agent
import json

res = link_analysis_agent.invoke(
    "Analise o link https://www.ifpi.edu.br/algum-doc.pdf"
)

print(res)  # Pode ser string ou AIMessage, dependendo da configuração
```

### 3.3 Comportamento esperado

O comportamento ideal é que o LLM:

1. Identifique que deve chamar a tool `analisar_link`
2. Execute a ferramenta
3. Retorne **exclusivamente o JSON** produzido pela tool

Caso o modelo responda com texto em linguagem natural, recomenda-se:

* Reforçar o prompt com:

  > “Retorne EXCLUSIVAMENTE um JSON, sem explicações.”
* Ou, no fluxo principal, **consumir diretamente o retorno da ferramenta**, ignorando o texto gerado pelo LLM.

---

## 4. Dica prática de validação

Para cada URL testada, valide manualmente os seguintes pontos:

### 4.1 Campo `status`

* `SUCESSO` → HTTP 200 e análise concluída
* `ERRO` → URL inválida, timeout, DNS, 404, etc.

### 4.2 Campo `tipo_conteudo`

* `PDF_DIRETO`
  → `proximo_agente` deve ser `AGENTE_EXTRACAO`
* `HTML_COM_PDF`
  → `pdfs_encontrados` deve listar todos os PDFs
* `HTML_TEXTO`
  → Texto mínimo válido e `proximo_agente="AGENTE_EXTRACAO"`
* `INVALIDO`
  → Deve conter justificativa clara em `observacoes`

### 4.3 Campo `pdfs_encontrados`

* URLs absolutas (links relativos devidamente resolvidos)
* Campo `descricao` preenchido com o texto âncora, quando existir

### 4.4 Campo `observacoes`

* Deve justificar claramente a decisão tomada:

  * Indícios de IFPI
  * Tipo de conteúdo
  * Texto insuficiente
  * Conteúdo irrelevante
  * Erro de acesso

