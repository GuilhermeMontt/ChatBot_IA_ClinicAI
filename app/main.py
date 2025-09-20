# app/main.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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

# --- Endpoints ---

@app.get("/")
async def root():
    triage = await get_convs()
    return {'data': triage}

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

    # Chama o agente para processar a mensagem
    reply_text, structured_data, is_emergency = await run_agent(user_id, chat)

    # Salva triagem parcial/atualizada no MongoDB

    # Salva resposta do agente no histórico
    await save_message(user_id, {"from": "agent", "text": reply_text})

    # Retorna resposta para o frontend
    return {"reply": reply_text}


