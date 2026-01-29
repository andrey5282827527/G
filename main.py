import os
import random
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- НАСТРОЙКИ ---
TOKEN = "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE"
# ОБЯЗАТЕЛЬНО: Впиши сюда свой URL из Render
WEBHOOK_URL = "https://g-15es.onrender.com/webhook"

# --- БАЗА ДАННЫХ ---
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True); username = Column(String, unique=True)
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True); sender = Column(String); receiver = Column(String); text = Column(Text); timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()
pending_auths = {}

# --- ОБРАБОТКА ТЕЛЕГРАМ ---
@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if text in pending_auths:
        username = message.from_user.username or f"id{message.from_user.id}"
        pending_auths[text] = {"username": username}
        with SessionLocal() as db:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username))
                db.commit()
        await message.answer(f"✅ Успех! Ты вошел как @{username}")
    else:
        await message.answer("Введите 6-значный код с сайта.")

# --- ЭНДПОИНТЫ ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.post("/request_code")
async def request_code():
    code = str(random.randint(100000, 999999))
    pending_auths[code] = None
    return {"code": code}

@app.get("/check_login/{code}")
async def check_login(code: str):
    if code in pending_auths and pending_auths[code]:
        return {"status": "success", "username": pending_auths[code]["username"]}
    return {"status": "waiting"}

@app.get("/messages")
async def get_history(me: str, with_user: str):
    with SessionLocal() as db:
        return db.query(Message).filter(((Message.sender==me)&(Message.receiver==with_user))|((Message.sender==with_user)&(Message.receiver==me))).all()

@app.post("/send")
async def send(sender: str, receiver: str, text: str):
    with SessionLocal() as db:
        db.add(Message(sender=sender, receiver=receiver, text=text)); db.commit()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("index.html", encoding="utf-8").read()

@app.on_event("startup")
async def on_startup():
    # Устанавливаем вебхук. Это "выбивает" всех polling-ботов.
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
