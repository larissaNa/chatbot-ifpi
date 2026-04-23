from typing import Any

from apps.authentication import ChatFeedback, ChatMessage


def serialize_message(message: ChatMessage, feedback_map: dict[int, str] | None = None) -> dict:
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "sender": message.sender,
        "content": message.content,
        "thoughts": message.thoughts,
        "feedback_rating": (feedback_map or {}).get(message.id),
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def serialize_history_payload(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [
        {
            "id": message.id,
            "sender": message.sender,
            "content": message.content,
        }
        for message in messages
    ]


def format_conversation_context(messages: list[ChatMessage], *, limit: int) -> str:
    items = messages[-limit:]
    lines: list[str] = []
    for message in items:
        content = (message.content or "").strip()
        if not content:
            continue
        role = "Usuário" if message.sender == "user" else "Assistente"
        lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def feedback_map_for_messages(messages: list[ChatMessage]) -> dict[int, str]:
    bot_ids = [message.id for message in messages if message.sender == "bot" and message.id]
    if not bot_ids:
        return {}

    rows = ChatFeedback.query.filter(ChatFeedback.bot_message_id.in_(bot_ids)).all()
    out: dict[int, str] = {}
    for row in rows:
        out[row.bot_message_id] = row.rating
    return out


def build_conversation_summaries(messages: list[ChatMessage], active_thread_id: str | None) -> list[dict]:
    grouped: dict[str, dict] = {}

    for message in messages:
        thread_id = message.thread_id
        item = grouped.setdefault(
            thread_id,
            {
                "thread_id": thread_id,
                "title": "Nova conversa",
                "last_message_preview": "",
                "last_message_at": None,
                "message_count": 0,
            },
        )
        item["message_count"] += 1
        item["last_message_preview"] = (message.content or "").strip()[:120]
        item["last_message_at"] = message.created_at.isoformat() if message.created_at else None

        if item["title"] == "Nova conversa" and message.sender == "user" and (message.content or "").strip():
            item["title"] = (message.content or "").strip()[:60]

    conversations = list(grouped.values())
    if active_thread_id and active_thread_id not in grouped:
        conversations.append(
            {
                "thread_id": active_thread_id,
                "title": "Nova conversa",
                "last_message_preview": "Sem mensagens ainda.",
                "last_message_at": None,
                "message_count": 0,
            }
        )
    conversations.sort(key=lambda item: item.get("last_message_at") or "", reverse=True)
    for item in conversations:
        item["is_active"] = item["thread_id"] == active_thread_id
    return conversations
