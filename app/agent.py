import logging

from dotenv import load_dotenv
from typing import List, Dict, TypedDict, Any
from app.utils import setup_model, extract_json, clean_llm_response

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()
logger = logging.getLogger("uvicorn.error")

model, EMERGENCY_KEYWORDS = setup_model()

# Definindo estado do grafo
class AgentState(TypedDict):
    chat_history: List[Dict]
    is_emergency: bool
    llm_response: str
    final_reply: str
    structured_data: Dict[str, Any]

# Definindo nós do grafo

def reset_state(state: AgentState) -> Dict[str, Any]:
    # Limpa campos do estado do grafo da execução anterior, para forçar nova execução
    return {
        "is_emergency": False,
        "llm_response": "",
        "final_reply": "",
        "structured_data": {}
    }

async def check_emergency(state: AgentState) -> Dict[str, Any]:
    # Nó que verifica a última mensagem por palavras-chave de emergência
    last_msg = state["chat_history"][-1]
    text = last_msg.get("text", "")
    lower = text.lower()
    if any(kw in lower for kw in EMERGENCY_KEYWORDS):
        return {"is_emergency": True}
    return {"is_emergency": False}

async def emergency_responder(state: AgentState) -> Dict[str, Any]:
    # Nó que gera a resposta padrão de emergência
    msg = ("Entendi. Seus sintomas podem indicar uma situação de emergência. "
           "Por favor, procure o pronto-socorro mais próximo ou ligue para o 192 imediatamente.")
    return {"final_reply": msg, "structured_data": {"emergency": True}}

async def call_llm(state: AgentState) -> Dict[str, Any]:
    # Nó que chama a API do Gemini
    chat_history = state["chat_history"]
    gemini_history = []
    for message in chat_history:
        role = "user" if message.get("from") == "user" else "model"
        gemini_history.append({"role": role, "parts": [message.get("text", "")]})
    
    try:
        response = await model.generate_content_async(gemini_history)
        return {"llm_response": response.text}
    except Exception as e:
        error_message = "Desculpe, estou com um problema técnico no momento e não consigo processar sua mensagem. Por favor, tente novamente em alguns instantes."
        logger.error(f"Erro na chamada da API Gemini: {e}")
        return {"final_reply": error_message, "structured_data": {}}

async def process_response(state: AgentState) -> Dict[str, Any]:
    # Nó que processa a resposta do LLM, extraindo o JSON.
    raw_text = state.get("llm_response", "")
    json_data = extract_json(raw_text)
    reply_text = clean_llm_response(raw_text)
    return {"final_reply": reply_text, "structured_data": json_data}


def should_continue(state: AgentState) -> str:
    # Decide o próximo passo com base na flag de emergência
    if state["is_emergency"]:
        return "emergency"
    # Se a resposta final já foi preenchida por um erro na chamada do LLM
    if state.get("final_reply"):
        return "end"
    return "continue"

# Contrução e compilação dos grafos

workflow = StateGraph(AgentState)

workflow.add_node("reset_state", reset_state)
workflow.add_node("check_emergency", check_emergency)
workflow.add_node("emergency_responder", emergency_responder)
workflow.add_node("call_llm", call_llm)
workflow.add_node("process_response", process_response)

workflow.set_entry_point("reset_state")
workflow.add_edge("reset_state", "check_emergency")
workflow.add_conditional_edges(
    "check_emergency",
    should_continue,
    {"emergency": "emergency_responder", "continue": "call_llm", "end": END}
)
workflow.add_edge("emergency_responder", END)
workflow.add_edge("call_llm", "process_response")
workflow.add_edge("process_response", END)

app = workflow.compile(checkpointer=MemorySaver())

async def run_agent(chat_id: str, chat: list):
    """Invoca o grafo LangGraph para processar a conversa."""
    initial_state = {"chat_history": chat}
    config = {"configurable": {"thread_id": chat_id}}
    final_state = await app.ainvoke(initial_state, config=config)
    
    return final_state['final_reply'], final_state['structured_data']
