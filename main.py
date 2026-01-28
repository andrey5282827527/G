import os
import random
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE")

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

app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальный словарь для кодов: { "654321": {"username": None, "active": True} }
pending_auths = {}

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Я бот Mini-Gram.\n\nВведи 6-значный код с сайта, чтобы подтвердить вход.")

@dp.message()
async def handle_code(message: types.Message):
    incoming_code = message.text.strip()
    print(f"--- БОТ ПОЛУЧИЛ ТЕКСТ: '{incoming_code}' ---")
    print(f"--- СЕЙЧАС В ПАМЯТИ ОЖИДАЮТСЯ: {list(pending_auths.keys())} ---")

    if incoming_code in pending_auths:
        # Берем username из Телеграма (если нет @username, берем ID)
        tg_user = message.from_user.username or f"id{message.from_user.id}"
        pending_auths[incoming_code] = {"username": tg_user, "active": True}
        
        with SessionLocal() as db:
            if not db.query(User).filter(User.username == tg_user).first():
                db.add(User(username=tg_user))
                db.commit()
        
        await message.answer(f"✅ Готово! Ты вошел как @{tg_user}. Возвращайся на вкладку с мессенджером.")
        print(f"--- УСПЕХ: Код {incoming_code} привязан к @{tg_user} ---")
    else:
        await message.answer("❌ Код не найден. Нажми 'Получить код' на сайте еще раз.")
        print(f"--- ОТКАЗ: Код {incoming_code} не найден в базе ---")

# --- API ---
@app.post("/request_code")
async def request_code():
    # Очищаем старые коды перед выдачей нового, чтобы не забивать память
    if len(pending_auths) > 100: pending_auths.clear()
    
    code = str(random.randint(100000, 999999))
    pending_auths[code] = None # Создаем пустую запись
    print(f"--- НОВЫЙ ЗАПРОС: Сгенерирован код {code} ---")
    return {"code": code}

@app.get("/check_login/{code}")
async def check_login(code: str):
    if code in pending_auths and pending_auths[code] is not None:
        return {"status": "success", "username": pending_auths[code]["username"]}
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
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Файл index.html не найден в папке с main.py"

@app.on_event("startup")
async def startup():
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

