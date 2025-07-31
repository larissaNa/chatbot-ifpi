import os
import getpass
from dotenv import load_dotenv
import uuid
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from typing import Annotated

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage
from langchain_core.tools import tool
from langchain.tools import Tool
from langchain_tavily import TavilySearch

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.document_loaders import PyPDFLoader # Carregar o PDF
from langchain.chains import RetrievalQA #RAG
import pypdf


# --- Autenticação ---
# Carrega as variáveis do arquivo .env
load_dotenv()

def _set_env(var: str):
    if not os.environ.get(var):
        raise EnvironmentError(f"A variável de ambiente {var} não está definida no arquivo .env")

# Verifica se as variáveis estão definidas
_set_env("TAVILY_API_KEY")
_set_env("ANTHROPIC_API_KEY")


llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

# Configura ChromaDB
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(
    collection_name="baseDeDados",
    embedding_function=embeddings,
    persist_directory="./chatbot"
)

# --- Ferramentas ---
tavily_tool = TavilySearch(max_results=2)
tools = [tavily_tool]

# --- Agente ReAct ---
agent = create_react_agent(model=llm, tools=tools)


# executar apenas uma vez
# Carregar PDFs
loader = PyPDFLoader("documentos/normativas.pdf")
pages = loader.load()

# Dividir em chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
docs = text_splitter.split_documents(pages)

# Inserir no ChromaDB
vectorstore.add_documents(docs)
vectorstore.persist()

# Ferramenta que consulta documentos internos
retriever = vectorstore.as_retriever(search_kwargs={"k": 6})

# Ferramenta que consulta documentos internos
institucional_qa = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

institucional_tool = Tool(
    name="consulta_institucional",
    func=lambda q: institucional_qa.invoke(q)["result"],
    description="Use esta ferramenta para responder perguntas sobre normativas, diretrizes, artigos ou documentos do IFPI."
)


# ---------- Ferramentas de segundo plano ----------
scheduler = BackgroundScheduler()

# Agente Tavily (busca geral)
tavily_agent = create_react_agent(
    model=llm,
    tools=[tavily_tool],
    prompt= 'You perform web searches',
    name="tavily_agent"
)

consulta_agent = create_react_agent(
    model=llm,
    tools=[institucional_tool],
    prompt="You respond only on the basis of internal IFPI documents.",
    name="consulta_institucional"
)

# --- Supervisor ---
supervisor_graph = create_supervisor(
    model=llm,
    agents=[tavily_agent, consulta_agent],
    prompt="""
Você é um supervisor inteligente.

Receba uma pergunta de um usuário e decida QUAL agente deve responder:

- Se a pergunta for sobre o IFPI, incluindo termos como: documentos institucionais, artigos acadêmicos, normas, resoluções, diretivas, eficiência energética, computação em nuvem ou temas internos → encaminhe para: consulta_institucional.

- Se a pergunta for sobre assuntos gerais, notícias, internet, atualidades, Google, etc → use Tavily.

Sempre escolha apenas UM agente. Após a resposta, resuma o que ele disse com uma explicação clara e direta ao usuário final.
""",
    add_handoff_messages=True,
    add_handoff_back_messages=True,
    output_mode="full_history"
)


# Compilar o gráfico do supervisor para torná-lo executável
compiled_supervisor = supervisor_graph.compile()

# --- Monta StateGraph e compila ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", compiled_supervisor)
graph.add_edge(START, "supervisor")
compiled = graph.compile(checkpointer=MemorySaver())


# ---------- 9. Loop interativo ----------
def run(user_input: str):
    thread_id = f"scheduler-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        for chunk in compiled.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
            stream_mode="values"
        ):
            for msg in chunk.get("messages", []):
                content = getattr(msg, "content", None)
                if isinstance(content, str) and content.strip():
                    msg.pretty_print()
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")

if __name__ == "__main__":
    print("Bem vindo ao chatbot IFPIA\n")
    while True:
        ui = input("User: ")
        if ui.lower() in ["exit","quit","q"]:
            print("Encerrando...")
            break
        run(ui)