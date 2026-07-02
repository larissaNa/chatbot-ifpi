# Chatbot Institucional do IFPI

Um **chatbot inteligente** desenvolvido para auxiliar alunos, professores e servidores do Instituto Federal do Piauí (IFPI) em consultas administrativas, acadêmicas e normativas. O sistema integra IA generativa com documentos institucionais, busca web e um pipeline multiagente, garantindo respostas rápidas, precisas e contextualizadas.

---

## Funcionalidades

- **RAG sobre documentos institucionais** — indexação semântica de PDFs, DOCX e TXT (até 150 MB) via ChromaDB, com suporte a tabelas, extração de texto estruturado e expansão de contexto.
- **Busca web (Tavily AI)** — acionada automaticamente quando os documentos locais não contêm a resposta. Fetcher robusto com fallback Playwright e suporte a proxy para evitar bloqueios (403).
- **Pipeline multiagente (LangGraph)** — supervisor classifica cada pergunta em três rotas: RAG institucional, busca web ou conversa contextual.
- **Modelo Gemini (Google)** — geração de respostas via `gemini-3.1-lite`.
- **Memória por thread** — mantém o contexto da conversa para perguntas de acompanhamento.
- **Fluxo de revisão de crenças** — pipeline de agentes que detecta mudanças semânticas em documentos já indexados e atualiza o ChromaDB automaticamente.
- **Modo produção público** — chatbot acessível sem login, controlado por variável de ambiente (`PROD_MODE`).
- **Painel administrativo** — visualização de conversas de usuários externos, feedbacks negativos (com modal de detalhes) e logs do sistema em tempo real.
- **Defesa contra prompt injection** — sanitização de queries e bloqueio de instruções maliciosas em documentos carregados (duas camadas).
- Interface web **Flask + Jinja2**, responsiva para mobile e desktop.
- Persistência em **PostgreSQL**, pronto para produção com **Docker Compose**.

---

## Arquitetura do Pipeline de Chat

```
Usuário → Supervisor (LangGraph)
              ├── RAG Local (ChromaDB + embeddings HuggingFace)
              ├── Busca Web (Tavily AI + fetcher robusto)
              └── Rota Conversacional (contexto + data atual)
                        └── Gemini LLM → Resposta
```

## Arquitetura do Pipeline de Indexação (Revisão de Crenças)

```
Link/Upload → Análise de Links → Extração (PDF/DOCX/TXT/HTML)
           → Processamento Semântico (chunking + embeddings)
           → Revisão de Crenças (comparação semântica)
           → ChromaDB (persistência vetorial)
```

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| LLM | Gemini 3.1 Lite (Google AI) |
| Orquestração | LangGraph |
| Busca vetorial | ChromaDB (persistente local) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (HuggingFace, normalize=True) |
| Busca web | Tavily AI + fetcher com Playwright |
| Backend | Flask + Jinja2 |
| Banco de dados | PostgreSQL 15 |
| Infraestrutura | Docker Compose + Nginx + Gunicorn |

---

## Requisitos

- Python 3.11+
- Docker e Docker Compose
- PostgreSQL 15+
- Dependências Python: `pip install -r requirements.txt`

---

## Instalação

1. Clone o repositório:

```bash
git clone https://github.com/larissaNa/chatbot-ifpi.git
cd chatbot-ifpi
```

2. Obtenha as chaves de API:

   - **Gemini:** [Google AI Studio](https://aistudio.google.com/) → APIs → Chave de API
   - **Tavily:** [tavily.com](https://tavily.com/) → Dashboard → API Keys

3. Configure o arquivo `.env` na raiz do projeto:

```env
# App
FLASK_APP=run.py
FLASK_DEBUG=1
DEBUG=True
SECRET_KEY=sua-chave-secreta

# APIs
GEMINI_API_KEY=your_gemini_key
TAVILY_API_KEY=your_tavily_key

# Modo produção (sem login, UI mínima)
# PROD_MODE=true

# Banco de dados
DB_ENGINE=postgresql
DB_HOST=db
DB_NAME=fastapi_db
DB_USERNAME=fastapi
DB_PASS=fastapi123
DB_PORT=5432

# Assets
ASSETS_ROOT=/static/assets
```

4. Suba os containers:

```bash
docker-compose up --build
```

5. Acesse:

```
http://localhost
```

---

## Uso

**Modo padrão (com login):**
- Cadastre-se e faça login
- Digite sua pergunta — o sistema busca nos documentos oficiais do IFPI e, se necessário, na web
- O histórico da conversa é mantido por thread

**Modo produção (`PROD_MODE=true`):**
- Chatbot público sem necessidade de cadastro
- Interface mínima, focada na conversa

**Painel Admin:**
- Acesse `/admin` para gerenciar documentos, ver conversas de usuários e monitorar logs do sistema

---

## Estrutura de Pastas (principais)

```
chatbot-ifpi/
├── apps/
│   ├── authentication/       # Models, login, rotas de auth
│   ├── core/
│   │   ├── chat/agents/      # supervisor, institutional_agent, web_agent
│   │   ├── documents/agents/ # belief_revision, chromadb, extraction, processing, link_analysis
│   │   └── utils/            # fetcher robusto, utilitários
│   └── home/                 # rotas principais, admin, feedback
├── docs/logica_agentes/      # Documentação técnica de cada agente
├── chroma_db/                # Banco vetorial persistente
├── crenças/                  # Documentos para o pipeline de revisão de crenças
├── nginx/                    # Configuração Nginx
├── docker-compose.yml
└── run.py
```

---

## Documentação Técnica

A lógica de cada agente está documentada em [`docs/logica_agentes/`](docs/logica_agentes/):

### Pipeline de Indexação de Documentos
- [Análise de Links](docs/logica_agentes/link_analysis_agent.MD)
- [Extração de Conteúdo](docs/logica_agentes/extraction_agent.MD)
- [Processamento Semântico](docs/logica_agentes/processing_agent.MD)
- [Revisão de Crenças](docs/logica_agentes/belief_revision_agent.MD)
- [ChromaDB (Persistência Vetorial)](docs/logica_agentes/chromadb_agent.MD)

### Pipeline de Conversação (Chat)
- [Supervisor de Rotas](docs/logica_agentes/supervisor_agent.MD)
- [Agente Institucional (RAG)](docs/logica_agentes/institutional_agent.MD)
- [Agente de Busca Web (Tavily)](docs/logica_agentes/web_agent.MD)

---

## Referências

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google AI Studio (Gemini)](https://aistudio.google.com/)
- [ChromaDB](https://www.trychroma.com/)
- [Tavily AI](https://tavily.com/)
- [Flask](https://flask.palletsprojects.com/)
- [PostgreSQL](https://www.postgresql.org/)

---

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

## Autora

**Larissa Souza do Nascimento** — Desenvolvimento do sistema multiagente e integração do chatbot institucional do IFPI.
