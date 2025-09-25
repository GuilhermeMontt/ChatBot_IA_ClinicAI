import logging, traceback, bson

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import create_chat, save_message, get_convs
from app.agent import run_agent

load_dotenv()

app = FastAPI(title="ClinicAI Triagem")

#  CORS para o frontend Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")

# Rotas

@app.get("/")
async def root():
    convs = await get_convs()
    return {'data': convs}

@app.post('/chat/new')
async def open_chat(request: Request):
    # Cria uma nova sessão de chat e retorna seu ID único
    chat_id = await create_chat()
    return {"chat_id": chat_id}

@app.post("/chat")
async def chat_endpoint(request: Request):
    # Recebe JSON e retorna JSON
    data = await request.json()
    chat_id = data.get("chat_id")
    text = data.get("message", "").strip()

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id é obrigatório")
    if not text:
        raise HTTPException(status_code=400, detail="Mensagem vazia")
    try:
        # Valida se o chat_id tem o formato de um ObjectId do MongoDB
        bson.ObjectId(chat_id)
    except bson.errors.InvalidId:
        raise HTTPException(status_code=400, detail="chat_id inválido")

    # Salva mensagem do usuário no histórico e recebe o histórico para enviar ao agent
    chat = await save_message(chat_id, {"from": "user", "text": text})
    try:
        # Chama o agente para processar a mensagem
        reply_text, structured_data = await run_agent(chat_id, chat)

        # Salva a resposta do agente e a triagem (se houver)
        agent_msg = {"from": "agent", "text": reply_text}
        if structured_data:
            await save_message(chat_id, agent_msg, triage=structured_data)
        else:
            await save_message(chat_id, agent_msg)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Erro no chat_endpoint: {e}\n{error_details}")
        return {"error": str(e)} 

    # Retorna resposta para o frontend
    return {"reply": reply_text}
