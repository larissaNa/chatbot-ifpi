# Agente de Extração – Implementação e Integração

Este documento descreve o agente responsável por extrair texto de documentos institucionais para indexação.

---

## 1. Onde está o Agente

* Arquivo: `apps/core/documents/agents/extraction_agent.py`
* Tool LangChain: `extrair_conteudo(analise: dict)`
* Dependências auxiliares:
  * `apps/core/documents/agents/download_utils.py` → `baixar_arquivo_resiliente(url)`
  * `apps/core/utils/fetcher.py` → `fetch_url_content(url)` (fetcher robusto com proxy e fallback Playwright)

---

## 2. Tipos de conteúdo suportados

| `tipo_conteudo` (entrada) | Aliases aceitos | Descrição |
|---|---|---|
| `PDF_DIRETO` | `PDF` | PDF acessível por URL |
| `DOCX` | `WORD` | Arquivo Word (.docx) |
| `TXT` | — | Arquivo de texto simples |
| `HTML_COM_PDF` | — | Página HTML contendo links para PDFs |
| `HTML_TEXTO` | `PAGINA` | Página HTML com conteúdo textual |

---

## 3. Lógica de extração por tipo

### 3.1 PDF (`PDF_DIRETO`)

Usa `baixar_arquivo_resiliente(url)` + PyMuPDF (`fitz`).

**Tratamento de tabelas (diferencial):**
1. Localiza tabelas na página via `page.find_tables()`
2. Obtém blocos de texto e ignora os que estão dentro de bboxes de tabelas
3. Tabelas são convertidas para **Markdown** + **texto verbalizado** (para melhor embedding):
   - Markdown: `| col1 | col2 |`
   - Verbalizado: `"Registro 1: campo é 'valor', ..."`
4. Todos os elementos (texto + tabelas) são ordenados pelo eixo Y para manter a ordem de leitura

**Detecção de PDF escaneado:**
- Calcula `ratio = páginas_com_texto / total_páginas` (mínimo 20 chars por página)
- `ratio >= 0.5` → `PDF_TEXTUAL`
- `ratio < 0.5` → `PDF_OCR` + observação (sem OCR real)

**Validação:** se o texto extraído tiver menos de 100 caracteres, retorna erro.

### 3.2 DOCX

Usa `baixar_arquivo_resiliente(url)` + `python-docx`. Extrai parágrafos e tabelas (células separadas por `|`). Normaliza e estima páginas por `len(texto) / 1800`.

### 3.3 TXT

Usa `baixar_arquivo_resiliente(url)` + `charset-normalizer` para detecção de encoding (fallback: UTF-8, depois Latin-1).

### 3.4 HTML com PDF (`HTML_COM_PDF`)

Itera sobre `pdfs_encontrados` da análise, extrai cada PDF individualmente via `_extract_from_pdf_url`. Se qualquer PDF for OCR, o `tipo_extracao_global` passa a ser `PDF_OCR`.

### 3.5 HTML texto (`HTML_TEXTO`)

Usa `fetch_url_content(url)` (fetcher robusto). Remove tags `script`, `style`, `nav`, `header`, `footer`, `aside`, `noscript`. Extrai texto de `h1–h6`, `p`, `li`.

---

## 4. Funções utilitárias

| Função | Responsabilidade |
|---|---|
| `_normalize_text(text)` | Remove espaços extras, normaliza quebras de linha, junta parágrafos com `\n\n` |
| `_detect_language(text)` | Heurística leve: ≥ 2 marcadores portugueses → `"pt"`, senão `"desconhecido"` |
| `_format_table_as_markdown(table)` | Converte tabela PyMuPDF para Markdown + texto verbalizado |

---

## 5. Saída do Agente (JSON)

**Sucesso:**
```json
{
  "fonte": "https://url-do-documento.pdf",
  "status": "sucesso",
  "tipo_extracao": "PDF_TEXTUAL",
  "documentos": [
    {
      "id_documento": "uuid-v4",
      "titulo": "Resolução 001/2024",
      "texto": "Texto extraído e normalizado...",
      "metadata": {
        "paginas_estimadas": 5,
        "idioma": "pt",
        "tipo_extracao": "PDF_TEXTUAL"
      }
    }
  ],
  "observacoes": "",
  "proximo_agente": "AGENTE_PROCESSAMENTO"
}
```

**Falha (nenhum conteúdo extraído):**
```json
{
  "fonte": "...",
  "status": "erro",
  "tipo_extracao": "PDF_TEXTUAL",
  "documentos": [],
  "observacoes": "Falha na extração: nenhum conteúdo textual útil encontrado.",
  "proximo_agente": "NENHUM"
}
```

---

## 6. Como testar

```python
from apps.core.documents.agents.extraction_agent import extrair_conteudo
import json

resultado = extrair_conteudo.invoke({
    "url": "https://www.ifpi.edu.br/documento.pdf",
    "tipo_conteudo": "PDF_DIRETO",
    "titulo": "Resolução 001/2024",
    "pdfs_encontrados": []
})

print(json.dumps(resultado, ensure_ascii=False, indent=2))
```
