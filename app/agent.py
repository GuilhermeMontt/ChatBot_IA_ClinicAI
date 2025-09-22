import re
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging


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

    # Constrói o histórico no formato esperado pelo Gemini
    history = []
    for message in chat:
        role = "user" if message.get("from") == "user" else "model"
        history.append({"role": role, "parts": [message.get("text", "")]})

    # Chama a API do Gemini de forma assíncrona e com tratamento de erros
    try:
        response = await model.generate_content_async(history)
        raw_text = response.text
    except Exception as e:
        logger.error(f"Erro na chamada da API Gemini para user_id '{user_id}': {e}")
        # Retorna uma mensagem de erro amigável e nenhum dado estruturado
        error_message = "Desculpe, estou com um problema técnico no momento e não consigo processar sua mensagem. Por favor, tente novamente em alguns instantes."
        return error_message, {}, False

    # tenta extrair JSON
    json_data = {}
    try:
        # Procura por um bloco de código JSON na resposta
        m = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if m:
            json_str = m.group(1)
            json_data = json.loads(json_str)
    except json.JSONDecodeError:
        # Se o JSON for inválido, o json_data continua vazio e o log pode ser adicionado se necessário
        json_data = {}

    # Usa o resumo do JSON se existir, caso contrário, usa a resposta de texto completa.
    reply_text = json_data.get("resumo", raw_text)

    return reply_text, json_data, False
