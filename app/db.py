import os
from app.utils import init_db
from datetime import datetime
from pymongo import ReturnDocument
from bson.objectid import ObjectId

db = init_db()

async def create_chat():
    # Cria um novo documento de chat e retorna seu ID.
    result = await db.conversations.insert_one({
        "chat": [],
        "triage": {},
        "timestamp": datetime.utcnow()
    })
    return str(result.inserted_id)

async def save_message(chat_id: str, msg_data: dict, triage: dict | None = None):
    """
    Salva uma mensagem no histórico e atualiza a triagem 
    Cria o chat se ele não existir, garantindo uma estrutura de documento consistente
    """
    query_filter = {"_id": ObjectId(chat_id)}
    update_query = {
        "$push": {"chat": msg_data}, 
        "$set": {"updated_at": datetime.utcnow()},
        "$setOnInsert": {
            "timestamp": datetime.utcnow()
        }
    }
    
    # Se triage for fornecido, uso $set 
    # Se não, $setOnInsert para inicializar o campo apenas na criação
    if triage:
        update_query["$set"]["triage"] = triage
    else:
        update_query["$setOnInsert"]["triage"] = {}

    # atualização e retorna o documento atualizado
    
    updated_conv = await db.conversations.find_one_and_update(
        query_filter,
        update_query,
        upsert=True,
        return_document=ReturnDocument.AFTER  # Garante que o documento retornado é o *após* a atualização
    )

    return updated_conv.get("chat", []) if updated_conv else []

async def get_convs():
    cursor =  db.conversations.find()
    # Converte o ObjectId para string 
    convs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        convs.append(doc)
    return convs
