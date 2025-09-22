import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from pymongo import ReturnDocument

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "clinicai")
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]

async def create_chat(user_id: str):
    """Salva cada mensagem (histórico bruto)"""
    # Usamos update_one com upsert para garantir que o chat seja criado apenas se não existir,
    # evitando erros de duplicação e tornando a operação mais robusta.
    await db.conversations.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "chat": [],
            "triage": {},
            "timestamp": datetime.utcnow()
        }},
        upsert=True
    )

async def save_message(user_id: str, msg_data: dict, triage: dict | None = None):
    """
    Salva uma mensagem no histórico e atualiza a triagem de forma atômica.
    Cria o chat se ele não existir, garantindo uma estrutura de documento consistente.
    """
    update_query = {
        "$push": {"chat": msg_data}, 
        "$set": {"updated_at": datetime.utcnow()},
        "$setOnInsert": {
            "timestamp": datetime.utcnow()
        }
    }
    # Lógica para evitar conflito de operadores:
    # Se 'triage' for fornecido, use $set (funciona para insert e update).
    # Se não, use $setOnInsert para inicializar o campo apenas na criação.
    if triage:
        update_query["$set"]["triage"] = triage
    else:
        update_query["$setOnInsert"]["triage"] = {}

    # Usamos find_one_and_update para fazer a atualização e retornar o documento atualizado
    # em uma única operação atômica, o que é mais eficiente.
    updated_conv = await db.conversations.find_one_and_update(
        {"user_id": user_id},
        update_query,
        upsert=True,
        return_document=ReturnDocument.AFTER  # Garante que o documento retornado é o *após* a atualização
    )

    # Retorna o histórico do chat do documento atualizado, evitando uma segunda chamada ao DB.
    # Se o documento for criado agora, updated_conv não será None.
    return updated_conv.get("chat", []) if updated_conv else []

async def get_convs():
    cursor =  db.conversations.find()
    # Converte o ObjectId para string para que seja serializável em JSON
    convs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        convs.append(doc)
    return convs
