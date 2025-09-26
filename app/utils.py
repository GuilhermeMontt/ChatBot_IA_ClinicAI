import os, json, re, logging

import google.generativeai as genai

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
logger = logging.getLogger("uvicorn.error")

# Funções do agente

def setup_model():
    api_key = os.getenv("GEMINI_API_KEY")  

    if not api_key:
        raise ValueError("⚠️ GEMINI_API_KEY não encontrada no .env")

    genai.configure(
        api_key=api_key
    )

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
    - Deixar claro: você NÃO substitui atendimento médico, NÃO pode realizar diagnóstico(Ex:"Isso me parece...") e NÃO sugerir tratamento
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
    
    Não precisa responder na sua resposta que produziu um JSON.

    Considere o max_output_token = 1500. Não mande uma resposta excedendo esse limite.

    """

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=generation_config,
        system_instruction=SYSTEM_PROMPT
    )

    return model, EMERGENCY_KEYWORDS

def extract_json(raw_text: str) -> dict:
    # Extrai um bloco de código JSON de uma string de texto
    json_data = {}
    try:
        m = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if m:
            json_str = m.group(1)
            json_data = json.loads(json_str)
            return json_data
    except json.JSONDecodeError:
        logger.warning("Não foi possível decodificar o JSON da resposta do LLM.")

    return {}

def clean_llm_response(raw_text: str) -> str:
    # Remove o bloco de código JSON
    cleaned_text = re.sub(r"```json\s*(\{.*?\})\s*```", "", raw_text, flags=re.DOTALL)
    return cleaned_text.strip()

# Funções do Banco de dados

def init_db():
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB", "clinicai")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    return db