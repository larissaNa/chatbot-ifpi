from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from langchain import hub

def create_tavily_tool():
    return TavilySearch(max_results=2)

prompt = hub.pull("hwchase17/react")

def create_tavily_agent(llm, tavily_tool):
    return create_react_agent(
        llm, 
        [tavily_tool],
        hub.pull("hwchase17/react"),
        name="tavily_agent"
)
