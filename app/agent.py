import re
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")  # pega GEMINI_API_KEY do .env automaticamente

if not api_key:
    raise ValueError("⚠️ GEMINI_API_KEY não encontrada no .env")

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-flash")

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

No fim, produza JSON válido com:
{
 "queixa": "...",
 "sintomas": "...",
 "duracao_frequencia": "...",
 "intensidade": "...",
 "historico": "...",
 "medidas_tomadas": "...",
 "resumo": "Resumo breve para o usuário"
}
"""

async def run_agent(user_id: str, chat: list):
    #buscando última mensagem
    last_msg = chat[-1]
    text = last_msg.get("text", "") if isinstance(last_msg, dict) else str(last_msg)
    lower = text.lower()

    # checagem rápida de emergência
    if any(kw in lower for kw in EMERGENCY_KEYWORDS):
        msg = ("Entendi. Seus sintomas podem indicar uma situação de emergência. "
               "Por favor, procure o pronto-socorro mais próximo ou ligue para o 192 imediatamente.")
        return msg, {"emergency": True}, True

    # chama Gemini
    prompt = SYSTEM_PROMPT
    for msg in chat[-10:]:
        role = "Usuário" if msg.get("from") == "user" else "ClinicAI"
        prompt += f"\n{role}: {msg.get('text')}"

    response = model.generate_content(prompt)
    raw_text = response.text if hasattr(response, "text") else str(response)

    # tenta extrair JSON
    json_data = {}
    try:
        m = re.search(r"(\{(?:.|\s)*\})", raw_text)
        if m:
            json_data = json.loads(m.group(1))
    except Exception:
        json_data = {}

    resumo = json_data.get("resumo", raw_text[:500])
    reply_text = (
                  f"{resumo}\n\nPosso continuar fazendo perguntas para completar sua triagem.")

    return reply_text, json_data, False
