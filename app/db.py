import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "clinicai")
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]

async def create_chat(user_id: str):
    """Salva cada mensagem (histórico bruto)"""
    chat=[]
    await db.conversations.insert_one({
        "user_id": user_id,
        "chat": chat,
        "timestamp": datetime.utcnow()
    })

async def save_message(user_id: str, triage_data: dict):
    """Insere/atualiza resumo estruturado da triagem"""
    await db.conversations.update_one(
        {"user_id": user_id},
        {"$set": {"structured": triage_data, "updated_at": datetime.utcnow()},
         "$push":{"chat": triage_data}},
        upsert=True
    )

    conv = await db.conversations.find_one({"user_id":user_id})

    return conv["chat"] if conv and "chat" in conv else []

async def get_convs():
    cursor =  db.triages.find()
    return [doc async for doc in cursor]
