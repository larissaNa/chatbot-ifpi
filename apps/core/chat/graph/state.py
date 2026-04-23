from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_profile: str
