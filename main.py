import os
import random
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- НАСТРОЙКИ ---
TOKEN = "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE"
WEBHOOK_URL = "https://g-15es.onrender.com/webhook"

# --- БАЗА ДАННЫХ (УПРОЩЕННАЯ) ---
class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    receiver = Column(String)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Создаем базу данных прямо сейчас
engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()
pending_auths = {}

# --- ОБРАБОТКА ТЕЛЕГРАМ ---
@dp.message()
async def handle_message(message: types.Message):
    code = message.text.strip()
    if code in pending_auths:
        username = message.from_user.username or f"id{message.from_user.id}"
        pending_auths[code] = {"username": username}
        await message.answer(f"✅ Вход выполнен: @{username}")
    else:
        await message.answer("Введите код с сайта.")

# --- ЭНДПОИНТЫ API ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
    return {"ok": True}

@app.post("/request_code")
def request_code():
    code = str(random.randint(100000, 999999))
    pending_auths[code] = None
    return {"code": code}

@app.get("/check_login/{code}")
def check_login(code: str):
    if code in pending_auths and pending_auths[code]:
        return {"status": "success", "username": pending_auths[code]["username"]}
    return {"status": "waiting"}

@app.get("/messages")
def get_history(me: str, with_user: str):
    db = SessionLocal()
    try:
        # Прямой запрос к базе
        msgs = db.query(Message).filter(
            ((Message.sender == me) & (Message.receiver == with_user)) |
            ((Message.sender == with_user) & (Message.receiver == me))
        ).order_by(Message.timestamp).all()
        
        # Форматируем в простой список словарей
        result = []
        for m in msgs:
            result.append({"sender": str(m.sender), "text": str(m.text)})
        return result
    except Exception as e:
        print(f"DATABASE ERROR (GET): {e}")
        return []
    finally:
        db.close()

@app.post("/send")
def send_msg(sender: str, receiver: str, text: str):
    if not text: return {"status": "error"}
    db = SessionLocal()
    try:
        new_msg = Message(sender=sender, receiver=receiver, text=text)
        db.add(new_msg)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        print(f"DATABASE ERROR (SEND): {e}")
        return {"status": "error"}
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
