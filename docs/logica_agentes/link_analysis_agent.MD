# Agente de Análise de Links – Implementação

Este documento descreve o agente que analisa e classifica URLs de documentos institucionais para iniciar o pipeline de indexação.

---

## 1. Onde está o Agente

* Arquivo: `apps/core/documents/agents/link_analysis_agent.py`
* Funções/tools expostas:
  * `buscar_documentos_oficiais()` — tool LangChain, busca todos os links ativos no banco de dados
  * `analisar_link(url: str)` — tool LangChain, analisa e classifica uma URL
  * `_analise_basica_url(url: str)` — função interna usada por `analisar_link`

---

## 2. Tool `buscar_documentos_oficiais`

Busca todos os `DocumentoOficial` com `ativo=True` no banco de dados. Para cada fonte:
- Se a URL terminar em `.pdf`, `.docx` ou `.txt` → adiciona diretamente à lista
- Senão → carrega a página com `fetch_url_content` e coleta todos os links `.pdf`, `.docx`, `.txt` encontrados nas tags `<a>`

Retorna uma lista de URLs únicas (via `set`).

---

## 3. Lógica de `_analise_basica_url`

### 3.1 URLs locais (`file://`)

Suporte completo a arquivos locais no Windows e Linux:
- Detecta o caminho real do arquivo (lida com os formatos `file://C:/`, `file:///C:/`, etc.)
- Classifica por extensão: `.pdf` → `PDF_DIRETO`, `.docx`/`.doc` → `DOCX`, `.txt` → `TXT`, outros → `HTML_TEXTO`
- Verifica existência e permissão de leitura antes de classificar

### 3.2 URLs remotas (http/https)

**Validação de acessibilidade:**
- Usa `requests.get(stream=True)` em vez de HEAD (evita 403 de servidores que bloqueiam HEAD)
- Se `stream=True` retornar 403, tenta `requests.get` normal como segundo esforço
- Usa headers de User-Agent real (Chrome) e proxy configurado via `get_proxies()`

**Atualização no banco (opcional):**
- Se houver contexto Flask ativo, atualiza `ultima_verificacao` e `ultimo_status_http` no `DocumentoOficial` correspondente

**Tratamento de 403 para PDFs:**
- Se a URL termina em `.pdf` e retornou 403, o agente ainda classifica como `PDF_DIRETO` e delega ao agente de extração tentar o download robusto (que usa Playwright/Jina como fallback).

### 3.3 Classificação por tipo de arquivo

| Condição | `tipo_conteudo` |
|---|---|
| MIME `application/pdf` ou URL termina em `.pdf` | `PDF_DIRETO` |
| MIME `officedocument.wordprocessingml` ou `.docx` | `DOCX` |
| MIME `text/plain` ou `.txt` | `TXT` |
| MIME com `html` | análise de HTML (ver abaixo) |
| Outro MIME | `INVALIDO` |

### 3.4 Análise de HTML

Usa `fetch_url_content(url)` (fetcher robusto com fallback Playwright). Com BeautifulSoup:
1. Extrai título da página
2. Coleta todos os links `.pdf` nas tags `<a>` (resolve URLs relativas)
3. Busca palavras-chave institucionais no título + texto (5000 chars): `ifpi`, `instituto federal do piauí`, `resolucao`, `portaria`, `norma`, `instrucao normativa`, `edital`, `comunicado`

**Classificação HTML:**

| Condição | `tipo_conteudo` |
|---|---|
| Encontrou PDFs na página | `HTML_COM_PDF` |
| Texto ≥ 50 caracteres | `HTML_TEXTO` |
| Texto < 50 caracteres | `INVALIDO` |

---

## 4. Formato de saída (JSON)

```json
{
  "url": "https://link-analisado",
  "status": "sucesso",
  "tipo_conteudo": "PDF_DIRETO",
  "titulo": null,
  "mime_type": "application/pdf",
  "pdfs_encontrados": [],
  "observacoes": "Indicios de documento oficial na URL: ifpi, resolucao",
  "proximo_agente": "AGENTE_EXTRACAO"
}
```

Valores possíveis:
- `status`: `"sucesso"` | `"erro"`
- `tipo_conteudo`: `"PDF_DIRETO"` | `"DOCX"` | `"TXT"` | `"HTML_COM_PDF"` | `"HTML_TEXTO"` | `"INVALIDO"`
- `proximo_agente`: `"AGENTE_EXTRACAO"` | `"NENHUM"`

---

## 5. Como usar

```python
from apps.core.documents.agents.link_analysis_agent import analisar_link, _analise_basica_url
import json

# Via tool LangChain
resultado = analisar_link.invoke({"url": "https://www.ifpi.edu.br/documento.pdf"})
print(json.dumps(resultado, ensure_ascii=False, indent=2))

# Via função interna (sem LangChain)
resultado = _analise_basica_url("https://www.ifpi.edu.br/documento.pdf")
```
