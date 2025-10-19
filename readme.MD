
# Chatbot Institucional do IFPI

Um **chatbot inteligente** desenvolvido para auxiliar alunos, professores e servidores do Instituto Federal do Piauí (IFPI) em consultas administrativas, acadêmicas e normativas. O sistema integra inteligência artificial com documentos institucionais, garantindo respostas rápidas, precisas e contextualizadas.

---

## 🛠 Funcionalidades

- Respostas baseadas em **documentos institucionais** (PDFs de normativas, resoluções e manuais).
- Integração com **LangGraph** e modelo **Claude (Anthropic)** para geração de respostas inteligentes.
- Busca semântica local com **ChromaDB**, permitindo consulta rápida de conteúdos relevantes.
- Pesquisa na web via **Tavily AI** para informações atualizadas.
- **Memória por thread**: mantém o contexto da conversa.
- Interface web **Flask + Jinja2** para interação amigável.
- Persistência de dados em **PostgreSQL**, pronto para produção com Docker Compose.

---


## ⚡ Requisitos

- Python 3.11+
- Docker e Docker Compose
- PostgreSQL 15+
- Dependências Python (instaladas via `pip install -r requirements.txt`)

---

## 🚀 Instalação

1. Clone o repositório:

```bash
git clone https://github.com/larissaNa/chatbot-ifpi.git
cd chatbot-ifpi
````

3. Pegar chave de API no gemini

GOOGLE AI STUDIO → APIS -→ CHAVE DE API

GOOGLE CLOUD → IAM e administrador → Contas de serviço → Criar conta de serviço →
“Chaves” → “Adicionar chave” → “Criar nova chave” → Formato JSON

2. Configure variáveis de ambiente (`.env`):

```env
DEBUG=True
TAVILY_API_KEY=your_tavily_key
GEMINI_API_KEY =your_gemini_key
FLASK_APP=run.py
FLASK_DEBUG=1

ASSETS_ROOT=/static/assets

DB_ENGINE=postgresql
DB_HOST=db
DB_NAME=fastapi_db
DB_USERNAME=fastapi
DB_PASS=fastapi123
DB_PORT=5432

```

3. Inicialize containers Docker:

```bash
docker-compose up --build
```

4. Acesse a interface web:

```
http://localhost
```

---

## 📝 Uso

* Cadastre-se no sistema
* Faça login com seu nome de usuário e senha
* Digite sua pergunta na interface web.
* O chatbot responderá utilizando **fontes oficiais** e dados recentes.
* Histórico da conversa é mantido por **thread**, permitindo continuidade do diálogo.

---

## 🔧 Contribuição

Contribuições são bem-vindas! Para colaborar:

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Faça commit das alterações (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

---

## 📚 Referências

* [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
* [Claude AI - Anthropic](https://www.anthropic.com/)
* [ChromaDB](https://www.trychroma.com/)
* [Tavily AI](https://tavily.com/)
* [Flask](https://flask.palletsprojects.com/)
* [PostgreSQL](https://www.postgresql.org/)

---

## ⚖️ Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

## 👩‍💻 Autor

**Larissa Souza do Nascimento** – Desenvolvimento do sistema multiagente e integração do chatbot institucional do IFPI.

```
