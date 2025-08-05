from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import BaseMessage
from typing import Annotated, TypedDict

from .tavily_agent import tavily_agent
from .consulta_agent import consulta_agent

llm_prompt = """
Você é um supervisor inteligente em um sistema de atendimento.

Sua função é receber uma pergunta do usuário e decidir qual dos dois agentes deve responder:

- Se for uma dúvida sobre regulamentos, documentos internos, lei 8112, ou processos institucionais do IFPI → envie para o agente `consulta_institucional`.
- Se for uma dúvida geral, sobre temas diversos, internet, curiosidades, notícias, etc. → envie para o agente `tavily_agent`.

Regras:
1. Sempre escolha apenas UM agente.
2. Se for a primeira interação com o usuário, cumprimente brevemente e explique sua função.
3. Se a mensagem do usuário estiver vaga ou incompleta, peça uma pergunta mais específica.
4. Não repita a introdução em interações seguintes.
5. No final, resuma brevemente o que o agente escolhido fará.

Exemplos de respostas:
- "Olá! Sou o supervisor e posso te ajudar. Vou encaminhar sua pergunta sobre normas do IFPI para nosso agente especializado."
- "Essa é uma pergunta mais geral. Vou direcionar para o agente de busca na internet para te ajudar melhor."

Seja claro, direto e evite repetir explicações.
"""

supervisor = create_supervisor(
    model=tavily_agent.llm,
    agents=[tavily_agent, consulta_agent],
    prompt=llm_prompt,
    add_handoff_messages=True,
    add_handoff_back_messages=True,
    output_mode="full_history"
)

class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", supervisor.compile())
graph.add_edge(START, "supervisor")
compiled_supervisor = graph.compile(checkpointer=MemorySaver())
