from apps.reports.agents.supervisor_agent import compiled_supervisor

thread_id = "web-chat"
interaction_count = 0

def run_chatbot(user_input: str):
    global thread_id, interaction_count

    if not user_input.strip():
        return "Por favor, digite uma pergunta válida."
    
     # reinicia thread_id a cada 30 interações
    if interaction_count >= 30:
        from uuid import uuid4
        thread_id = str(uuid4())
        interaction_count = 0

    config = {"configurable": {"thread_id": "web-chat"}}
    last_valid_response = ""
    interaction_count += 1

    try:
        for chunk in compiled_supervisor.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
            stream_mode="values"
        ):
            for msg in chunk.get("messages", []):
                content = getattr(msg, "content", None)
                if isinstance(content, str) and content.strip():
                    # Ignorar mensagens técnicas
                    if any(kw in content.lower() for kw in [
                        "successfully transferred",
                        "transferring",
                        "transferring back",
                        "enviando para",
                        "enviado para"
                    ]):
                        print(f"[DEBUG] ⚙️ {content}")
                        continue
                    last_valid_response = content.strip()
    except Exception as e:
        last_valid_response = f"Erro: {str(e)}"

    return last_valid_response
