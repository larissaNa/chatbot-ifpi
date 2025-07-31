from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from apps import db

from apps.reports import blueprint
from apps.reports.services.utils import setup_vectorstore
from apps.reports.agents.tavily_agent import create_tavily_tool, create_tavily_agent
from apps.reports.agents.agent_consulta_institucional import create_consulta_institucional_agent
from apps.reports.orchestrator import create_supervisor_graph

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain import hub
import uuid

# Inicializa modelos e agentes
llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")
vectorstore = setup_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 6})

tavily_tool = create_tavily_tool()
consulta_tool = create_consulta_institucional_agent(llm, retriever)

prompt = hub.pull("hwchase17/react")

tools = [consulta_tool]
consulta_agent = create_react_agent(llm, tools, prompt, name="consulta_institucional")

tavily_agent = create_tavily_agent(llm, tavily_tool)

compiled_graph = create_supervisor_graph(llm, [tavily_agent, consulta_agent])

@blueprint.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        data = request.get_json()
        user_input = data.get("message", "")
        if not user_input:
            return jsonify({"reply": "❌ Nenhuma mensagem recebida."}), 400

        thread_id = f"scheduler-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        response_text = ""

        for chunk in compiled_graph.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
            stream_mode="values"
        ):
            for msg in chunk.get("messages", []):
                content = getattr(msg, "content", None)
                if isinstance(content, str) and content.strip():
                    response_text += content.strip() + "\n"

        return jsonify({"reply": response_text.strip()})
    except Exception as e:
        print(f"Erro no chatbot: {e}")
        return jsonify({"reply": "❌ Erro interno ao processar sua mensagem."}), 500
