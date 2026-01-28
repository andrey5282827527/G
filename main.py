import os
import random
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
TOKEN = "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE"

# --- БАЗА ДАННЫХ ---
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    receiver = Column(String)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()
pending_auths = {} # { "123456": "username" или None }

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Введи 6-значный код с сайта Mini-Gram, чтобы войти.")

@dp.message()
async def handle_code(message: types.Message):
    code = message.text.strip()
    if code in pending_auths:
        username = message.from_user.username or f"user_{message.from_user.id}"
        pending_auths[code] = username # Подтверждаем вход
        
        # Сохраняем юзера в базу
        with SessionLocal() as db:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username))
                db.commit()
                
        await message.answer(f"✅ Успешно! Ты вошел как @{username}. Теперь вернись на сайт.")
    else:
        await message.answer("❌ Неверный код или срок его действия истек.")

# --- API ЭНДПОИНТЫ ---
@app.post("/request_code")
async def request_code():
    code = str(random.randint(100000, 999999))
    pending_auths[code] = None
    return {"code": code}

@app.get("/check_login/{code}")
async def check_login(code: str):
    if code in pending_auths and pending_auths[code] is not None:
        return {"status": "success", "username": pending_auths[code]}
    return {"status": "waiting"}

@app.get("/messages")
async def get_messages(me: str, with_user: str):
    with SessionLocal() as db:
        return db.query(Message).filter(
            ((Message.sender == me) & (Message.receiver == with_user)) |
            ((Message.sender == with_user) & (Message.receiver == me))
        ).order_by(Message.timestamp).all()

@app.post("/send")
async def send_msg(sender: str, receiver: str, text: str):
    with SessionLocal() as db:
        db.add(Message(sender=sender, receiver=receiver, text=text))
        db.commit()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("index.html", encoding="utf-8").read()

# Запуск бота в фоне
@app.on_event("startup")
async def startup():
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
