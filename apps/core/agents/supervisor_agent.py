from langgraph_supervisor import create_supervisor
from .tavily_agent import tavily_agent
from .consulta_agent import consulta_agent
from ..llm_config import get_llm
from .prompt import get_llm_prompt

llm = get_llm()
llm_prompt = get_llm_prompt()

supervisor = create_supervisor(
    model=llm,
    agents=[tavily_agent, consulta_agent],
    prompt=llm_prompt
).compile()