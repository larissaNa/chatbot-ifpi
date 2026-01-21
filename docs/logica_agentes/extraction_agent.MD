# Agente de Extração – Implementação e Integração



Este documento descreve:

* Onde o agente está no código
* Qual a entrada esperada (vinda do Agente de Análise de Links)
* Como funciona a extração para PDF e HTML
* O formato exato do JSON de saída
* Como testar o agente na prática

---

## 1. Onde está o Agente de Extração

### 1.1 Implementação principal

* Arquivo:
  `apps/core/agents/extraction_agent.py`
* Tool LangChain:
  `extrair_conteudo(analise: dict)`

### 1.2 Integração como agente ReAct

* Arquivo:
  `apps/core/agents/react_agents.py`
* Agente criado:

  ```python
  extraction_agent = create_react_agent(
      ...,
      tools=[extrair_conteudo],
      ...
  )
  ```

O agente foi projetado para receber **diretamente o JSON produzido pelo Agente de Análise de Links**, sem necessidade de adaptação intermediária.

---

## 2. Entrada esperada pelo Agente de Extração

O tool `extrair_conteudo` recebe um `dict` Python (ou JSON equivalente) contendo, no mínimo:

```json
{
  "url": "https://algo",
  "tipo_conteudo": "PDF_DIRETO | HTML_COM_PDF | HTML_TEXTO",
  "titulo": "opcional",
  "pdfs_encontrados": [
    {
      "url": "https://link-do-pdf.pdf",
      "descricao": "texto do link"
    }
  ]
}
```

📌 **Observação importante**
Você pode passar **diretamente a saída do `analisar_link`**, pois o formato é compatível por design.

---

## 3. Lógica de extração implementada

Toda a lógica reside em funções auxiliares dentro de:

* `apps/core/agents/extraction_agent.py`

### 3.1 Funções utilitárias

#### `_normalize_text(text: str) -> str`

Responsável por:

* Remover quebras de linha excessivas
* Normalizar espaços em branco
* Preservar parágrafos separados por linhas em branco

#### `_detect_language(text: str) -> str`

Heurística leve de detecção de idioma:

* Se encontrar marcadores comuns do português
  (ex.: `" que "`, `" de "`, `" não "`, `"ção"`, `" art. "`) em quantidade mínima → `"pt"`
* Caso contrário → `"desconhecido"`

---

## 3.2 Extração de PDFs

### Função

```python
_extract_from_pdf_url(url: str)
```

### Fluxo de execução

1. **Download do PDF**

   * `requests.get(url, timeout=30)`
   * Se erro de rede ou status ≠ 200:

     * Texto vazio
     * `paginas = 0`
     * Observação técnica:

       * `"Erro ao baixar PDF: ..."` ou
       * `"status HTTP ..."`

2. **Abertura com PyMuPDF (fitz)**

   * `fitz.open(stream=resp.content, filetype="pdf")`
   * Em caso de falha:

     * Observação: `"Erro ao abrir PDF: ..."`

3. **Extração de texto**

   * Para cada página:

     ```python
     page.get_text("text")
     ```
   * Armazena o tamanho do texto por página

4. **Detecção de PDF textual vs escaneado**

   * `pages_with_text`: páginas com ≥ 20 caracteres
   * `ratio = pages_with_text / total_paginas`

   Classificação:

   * `ratio >= 0.5` → `PDF_TEXTUAL`
   * `ratio < 0.5` → `PDF_OCR`

   Se `PDF_OCR`, adiciona observação:

   ```
   PDF provavelmente escaneado. OCR não aplicado ou incompleto.
   ```

   📌 **Observação**

   * Não executa OCR real
   * Não inventa texto
   * Cumpre a regra: *“Se OCR falhar, informe em observacoes”*

5. **Normalização**

   * Junta o texto de todas as páginas
   * Aplica `_normalize_text`

### Retorno interno da função

```python
texto_normalizado, paginas, tipo_extracao, observacoes_lista
```

---

## 3.3 Extração de HTML

### Função

```python
_extract_from_html_url(url: str)
```

### Fluxo de execução

1. **Download do HTML**

   * `requests.get(url, timeout=30)`
   * Se erro ou status ≠ 200:

     * Observação técnica correspondente

2. **Parsing**

   * `BeautifulSoup(html, "lxml")`

3. **Remoção de elementos irrelevantes**

   * `script`, `style`, `nav`, `header`, `footer`, `aside`, `noscript`

4. **Extração do título**

   * `soup.find("title")`
   * Se existir e não for vazio → `titulo`

5. **Extração do conteúdo principal**

   * Percorre:

     * `h1`–`h6`, `p`, `li`
   * Usa:

     ```python
     tag.get_text(" ", strip=True)
     ```
   * Fallback:

     * `soup.get_text(" ", strip=True)`

6. **Normalização**

   * Junta todo o texto
   * Aplica `_normalize_text`

7. **Estimativa de páginas**

   * Se houver texto:

     ```python
     paginas_estimadas = max(1, int(len(texto) / 1800))
     ```
   * Se não houver texto:

     * `paginas_estimadas = 0`
     * Observação:

       ```
       Nenhum conteúdo textual significativo encontrado no HTML.
       ```

### Retorno interno

```python
titulo, texto_normalizado, paginas_estimadas, observacoes_lista
```

---

## 4. Comportamento por tipo de conteúdo

A lógica principal está em:

```python
extrair_conteudo(analise: dict)
```

### 4.1 Campos básicos

* `fonte`: `analise["url"]` ou `analise["fonte"]`
* `tipo_conteudo`: `analise["tipo_conteudo"]`
* `pdfs`: `analise.get("pdfs_encontrados", [])`

---

### 4.2 `PDF_DIRETO`

* Executa `_extract_from_pdf_url(fonte)`
* Cria um documento:

```python
{
  "id_documento": str(uuid.uuid4()),
  "titulo": analise.get("titulo"),
  "texto": texto_extraido,
  "paginas_estimadas": paginas,
  "idioma": idioma_detectado
}
```

* `tipo_extracao_global`:

  * `"PDF_TEXTUAL"` ou `"PDF_OCR"`

---

### 4.3 `HTML_COM_PDF`

* Para cada item em `pdfs_encontrados`:

  * Chama `_extract_from_pdf_url(item["url"])`
  * Cria um documento por PDF

```python
{
  "id_documento": str(uuid.uuid4()),
  "titulo": item.get("descricao") or analise.get("titulo"),
  "texto": texto_extraido,
  "paginas_estimadas": paginas,
  "idioma": idioma_detectado
}
```

* Regra de prioridade:

  * Se **qualquer** PDF for `PDF_OCR` → `tipo_extracao_global = "PDF_OCR"`
  * Caso contrário → `"PDF_TEXTUAL"`

* Caso inconsistente:

  * `HTML_COM_PDF` sem PDFs → observação registrada

---

### 4.4 `HTML_TEXTO`

* Executa `_extract_from_html_url(fonte)`
* Cria um único documento
* Define:

  * `tipo_extracao_global = "HTML"`

---

### 4.5 Tipos não suportados

* Considerados inválidos:

  * Observação explicativa
  * `documentos` vazio
  * `tipo_extracao_global = "HTML"` (fallback técnico)

---

## 5. JSON de saída (formato final)

A função `extrair_conteudo` retorna **sempre**:

```python
{
  "fonte": fonte,
  "tipo_extracao": tipo_extracao_global or "HTML",
  "documentos": documentos,
  "observacoes": " ".join(observacoes).strip(),
  "proximo_agente": "AGENTE_PROCESSAMENTO"
}
```

📌 O formato é **fixo**, previsível e compatível com o próximo agente do fluxo.

---

## 6. Como testar o Agente de Extração

### 6.1 Acessar o container

```bash
docker-compose exec appseed_app bash
```

### 6.2 Executar o teste no Python

```python
from apps.core.agents.search_agent import _analise_basica_url
from apps.core.agents.extraction_agent import extrair_conteudo
import json

url = "https://www.ifpi.edu.br/algum-documento.pdf"
analise = _analise_basica_url(url)

resultado = extrair_conteudo(analise)

print(json.dumps(resultado, ensure_ascii=False, indent=2))
```

### 6.3 Cenários recomendados

* **PDF_DIRETO**
  → Um único documento no array `documentos`
* **HTML_COM_PDF**
  → Um documento por PDF encontrado
* **HTML_TEXTO**
  → Um único documento com texto limpo

