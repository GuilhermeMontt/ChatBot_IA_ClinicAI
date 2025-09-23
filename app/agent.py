import re
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict, TypedDict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")  # pega GEMINI_API_KEY do .env automaticamente

if not api_key:
    raise ValueError("⚠️ GEMINI_API_KEY não encontrada no .env")

genai.configure(
    api_key=api_key
)

logger = logging.getLogger("uvicorn.error")

generation_config = {
    "temperature": 0.4,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 1500,
    "response_mime_type": "text/plain",
}

# palavras-chave que disparam protocolo de emergência
EMERGENCY_KEYWORDS = [
    "dor no peito", "falta de ar", "desmaio",
    "sangramento intenso", "convulsão", "parou de respirar"
]

SYSTEM_PROMPT = """
Você é ClinicAI, um assistente virtual de triagem médica.

Comportamento: O agente deve ser acolhedor, empático, calmo e profissional. Ele precisa guiar o usuário de forma paciente durante a conversa, fazendo-o se sentir seguro para compartilhar suas informações.
Tom de Voz: Use uma linguagem clara, simples e direta. Evite jargões profissional de saúdes. A comunicação deve ser humanizada, mas sem ser excessivamente informal.

Missão:
- Deixar claro: você NÃO substitui atendimento médico.
- Coletar informações estruturadas:
  - queixa principal
  - sintomas
  - duração e frequência
  - intensidade (0 a 10)
  - histórico relevante
  - medidas já tomadas
- Não diagnostique, não prescreva.
- Se identificar emergência, diga para procurar pronto-socorro ou ligar 192.

No fim, ao coletar todas essas informações, produza JSON válido com:
{
 "queixa": "...",
 "sintomas": "...",
 "duracao_frequencia": "...",
 "intensidade": "...",
 "historico": "...",
 "medidas_tomadas": "...",
 "resumo": "Resumo breve para o usuário"
}

Considere o max_output_token = 1500. Não mande uma resposta excedendo esse limite.

"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=SYSTEM_PROMPT
)

# --- 1. Definição do Estado do Grafo ---
class AgentState(TypedDict):
    """Representa o estado do nosso agente em cada passo."""
    chat_history: List[Dict]
    is_emergency: bool
    llm_response: str
    final_reply: str
    structured_data: Dict[str, Any]

# --- 2. Definição dos Nós do Grafo ---

def reset_state(state: AgentState) -> Dict[str, Any]:
    """Limpa os campos de resultado do estado anterior para forçar uma nova execução."""
    return {
        "is_emergency": False,
        "llm_response": "",
        "final_reply": "",
        "structured_data": {}
    }

async def check_emergency(state: AgentState) -> Dict[str, Any]:
    """Nó que verifica a última mensagem por palavras-chave de emergência."""
    last_msg = state["chat_history"][-1]
    text = last_msg.get("text", "")
    lower = text.lower()
    if any(kw in lower for kw in EMERGENCY_KEYWORDS):
        return {"is_emergency": True}
    return {"is_emergency": False}

async def emergency_responder(state: AgentState) -> Dict[str, Any]:
    """Nó que gera a resposta padrão de emergência."""
    msg = ("Entendi. Seus sintomas podem indicar uma situação de emergência. "
           "Por favor, procure o pronto-socorro mais próximo ou ligue para o 192 imediatamente.")
    return {"final_reply": msg, "structured_data": {"emergency": True}}

async def call_llm(state: AgentState) -> Dict[str, Any]:
    """Nó que chama a API do Gemini."""
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
        return {"final_reply": error_message}

async def process_response(state: AgentState) -> Dict[str, Any]:
    """Nó que processa a resposta do LLM, extraindo o JSON."""
    raw_text = state["llm_response"]
    json_data = {}
    try:
        m = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if m:
            json_str = m.group(1)
            json_data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("Não foi possível decodificar o JSON da resposta do LLM.")
        json_data = {}
    
    reply_text = json_data.get("resumo", raw_text)
    return {"final_reply": reply_text, "structured_data": json_data}

# --- 3. Definição da Borda Condicional ---

def should_continue(state: AgentState) -> str:
    """Decide o próximo passo com base na flag de emergência."""
    if state["is_emergency"]:
        return "emergency"
    # Se a resposta final já foi preenchida por um erro na chamada do LLM
    if state.get("final_reply"):
        return "end"
    return "continue"

# --- 4. Construção e Compilação do Grafo ---

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

# --- 5. Função de Interface Atualizada ---

async def run_agent(chat_id: str, chat: list):
    """Invoca o grafo LangGraph para processar a conversa."""
    initial_state = {"chat_history": chat}
    config = {"configurable": {"thread_id": chat_id}}
    final_state = await app.ainvoke(initial_state, config=config)
    
    return final_state['final_reply'], final_state['structured_data'], final_state['is_emergency']
