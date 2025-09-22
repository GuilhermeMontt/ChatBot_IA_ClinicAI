# app/main.py
import os, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging, traceback
from app.db import create_chat, save_message, get_convs
from app.agent import run_agent

load_dotenv()

app = FastAPI(title="ClinicAI Triagem")

# --- CORS (para o frontend Lovable) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção, restrinja para o domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")  # usa o logger do uvicorn
# --- Endpoints ---

@app.get("/")
async def root():
    convs = await get_convs()
    return {'data': convs}

@app.post('/chat/new')
async def open_chat(request: Request):
    data = await request.json()
    user_id = data.get('user_id', 'anon')

    await create_chat(user_id)
    return{"message":"chat criado com sucesso"}

@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    Recebe JSON:
        {
            "user_id": "usuario123",
            "message": "Olá, estou com dor de cabeça"
        }
    Retorna JSON:
        {
            "reply": "Resposta do agente"
        }
    """
    data = await request.json()
    user_id = data.get("user_id", "anon")
    text = data.get("message", "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Mensagem vazia")

    # Salva mensagem do usuário no histórico e recebe o histórico para enviar ao agent
    chat = await save_message(user_id, {"from": "user", "text": text})
    try:
        # Chama o agente para processar a mensagem
        reply_text, structured_data, is_emergency = await run_agent(user_id, chat)

        # Salva a resposta do agente e a triagem (se houver)
        agent_msg = {"from": "agent", "text": reply_text}
        if structured_data:
            await save_message(user_id, agent_msg, triage=structured_data)
        else:
            await save_message(user_id, agent_msg)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Erro no chat_endpoint: {e}\n{error_details}")
        return {"error": str(e)}  # opcional: devolver erro pro cliente

    # Retorna resposta para o frontend
    return {"reply": reply_text}
