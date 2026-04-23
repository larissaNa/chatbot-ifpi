import re

from apps import db
from apps.authentication import ChatMessage, UserMemory


def extract_memory_candidates(text: str) -> dict[str, str]:
    content = (text or "").strip()
    lowered = content.lower()
    if not content:
        return {}

    memories: dict[str, str] = {}

    name_patterns = [
        r"\bmeu nome é\s+([a-zà-ÿ][a-zà-ÿ\s'-]{1,40})",
        r"\bpode me chamar de\s+([a-zà-ÿ][a-zà-ÿ\s'-]{1,40})",
        r"\bme chamo\s+([a-zà-ÿ][a-zà-ÿ\s'-]{1,40})",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            memories["nome"] = match.group(1).strip(" .,!?:;").title()
            break

    role_match = re.search(
        r"\beu sou\s+(aluno|aluna|professor|professora|servidor|servidora|docente|técnico|tecnica|técnica)",
        lowered,
        flags=re.IGNORECASE,
    )
    if role_match:
        memories["perfil"] = role_match.group(1).strip().lower()

    if any(token in lowered for token in ["resposta curta", "respostas curtas", "seja breve", "objetivo"]):
        memories["estilo_resposta"] = "curta e objetiva"
    elif any(token in lowered for token in ["resposta detalhada", "respostas detalhadas", "explique melhor", "mais detalhes"]):
        memories["estilo_resposta"] = "detalhada"

    preference_match = re.search(
        r"\b(?:prefiro|gosto de|tenho interesse em)\s+(.+?)(?:[.!?]|$)",
        content,
        flags=re.IGNORECASE,
    )
    if preference_match:
        memories["preferencia"] = preference_match.group(1).strip()

    return memories


def extract_memories_from_messages(messages: list[ChatMessage]) -> dict[str, str]:
    memory_map: dict[str, str] = {}
    for message in messages:
        if message.sender != "user":
            continue
        memory_map.update(extract_memory_candidates(message.content or ""))
    return memory_map


def load_user_memories(*, user_id: int | None, thread_id: str) -> dict[str, str]:
    query = UserMemory.query
    if user_id is not None:
        rows = (
            query.filter_by(user_id=user_id)
            .order_by(UserMemory.updated_at.desc(), UserMemory.id.desc())
            .all()
        )
    else:
        rows = (
            query.filter_by(thread_id=thread_id)
            .order_by(UserMemory.updated_at.desc(), UserMemory.id.desc())
            .all()
        )

    memory_map: dict[str, str] = {}
    for row in rows:
        if row.memory_key not in memory_map and row.memory_value:
            memory_map[row.memory_key] = row.memory_value
    return memory_map


def format_user_profile(memory_map: dict[str, str]) -> str:
    if not memory_map:
        return ""

    labels = {
        "nome": "Nome",
        "perfil": "Perfil",
        "estilo_resposta": "Estilo de resposta preferido",
        "preferencia": "Preferência declarada",
    }
    lines = []
    for key, value in memory_map.items():
        label = labels.get(key, key.replace("_", " ").title())
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def persist_user_memories(
    *,
    user_id: int | None,
    thread_id: str,
    source_message_id: int | None,
    memory_candidates: dict[str, str],
) -> None:
    if not memory_candidates:
        return

    for key, value in memory_candidates.items():
        if not value:
            continue
        query = UserMemory.query.filter_by(memory_key=key)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        else:
            query = query.filter_by(thread_id=thread_id)

        row = query.order_by(UserMemory.updated_at.desc(), UserMemory.id.desc()).first()
        if row:
            row.memory_value = value
            row.source_message_id = source_message_id
            row.confidence = 1.0
        else:
            row = UserMemory(
                user_id=user_id,
                thread_id=None if user_id is not None else thread_id,
                memory_key=key,
                memory_value=value,
                source_message_id=source_message_id,
                confidence=1.0,
            )
            db.session.add(row)
    db.session.commit()


def build_effective_user_profile(
    *,
    user_id: int | None,
    thread_id: str,
    history_messages: list[ChatMessage],
    current_user_input: str | None = None,
) -> tuple[dict[str, str], str, dict[str, str]]:
    history_memories = extract_memories_from_messages(history_messages)
    stored_memories = load_user_memories(user_id=user_id, thread_id=thread_id)
    current_message_memories = extract_memory_candidates(current_user_input or "")

    effective_memories = history_memories.copy()
    effective_memories.update(stored_memories)
    effective_memories.update(current_message_memories)

    return effective_memories, format_user_profile(effective_memories), current_message_memories
