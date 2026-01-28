import os
import random
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime
import uvicorn
from telegram import Bot

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") # Токен от BotFather
bot = Bot(token=TELEGRAM_TOKEN)

# --- БАЗА ДАННЫХ ---
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True) # Твой ник в ТГ
    tg_id = Column(String, unique=True)    # Твой ID в ТГ

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    receiver = Column(String) # Чтобы можно было искать по юзу
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
# Словарь для хранения временных кодов { "код": "статус_ожидания" }
pending_auths = {}

# --- API ---
@app.post("/request_access")
async def request_access():
    auth_code = str(random.randint(100000, 999999))
    pending_auths[auth_code] = {"status": "pending", "username": None}
    return {"auth_code": auth_code}

@app.get("/check_auth/{code}")
async def check_auth(code: str):
    if code in pending_auths and pending_auths[code]["status"] == "success":
        user_data = pending_auths[code]
        # Сохраняем в базу, если новый
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == user_data["username"]).first()
            if not user:
                new_user = User(username=user_data["username"])
                db.add(new_user)
                db.commit()
        return {"status": "ok", "username": user_data["username"]}
    return {"status": "waiting"}

@app.post("/send_msg")
async def send_msg(sender: str, receiver: str, text: str):
    with SessionLocal() as db:
        msg = Message(sender=sender, receiver=receiver, text=text)
        db.add(msg)
        db.commit()
    return {"status": "ok"}

@app.get("/get_history")
async def get_history(user1: str, user2: str):
    with SessionLocal() as db:
        msgs = db.query(Message).filter(
            ((Message.sender == user1) & (Message.receiver == user2)) |
            ((Message.sender == user2) & (Message.receiver == user1))
        ).order_by(Message.timestamp).all()
        return msgs

# --- ТУТ БУДЕТ ЛОГИКА БОТА (В идеале отдельный скрипт, но можно и тут) ---
# Для простоты: ты должен будешь отправить боту этот код.
# В реальности мы напишем маленькую функцию для обработки команд бота.

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("index.html", encoding="utf-8").read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
