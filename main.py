import os
import random
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
# Берем токен из переменной окружения Render или используем твой напрямую
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
    sender = Column(String)    # Кто отправил
    receiver = Column(String)  # Кому (юзернейм)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Временное хранилище кодов в памяти сервера
# { "код": {"username": None} }
pending_auths = {}

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Это бот Mini-Gram.\n\nВведи 6-значный код с сайта, чтобы войти в свой аккаунт.")

@dp.message()
async def handle_code(message: types.Message):
    code = message.text.strip()
    print(f"--- БОТ ПОЛУЧИЛ КОД: {code} ---")
    
    if code in pending_auths:
        # Берем юзернейм из ТГ (если нет @, создаем на основе ID)
        username = message.from_user.username or f"user_{message.from_user.id}"
        pending_auths[code] = {"username": username}
        
        # Сохраняем пользователя в базу данных
        with SessionLocal() as db:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username))
                db.commit()
        
        await message.answer(f"✅ Авторизация успешна! Вы вошли как @{username}.\nТеперь вернитесь на сайт.")
        print(f"--- УСПЕХ: @{username} вошел по коду {code} ---")
    else:
        await message.answer("❌ Код неверный или устарел. Получи новый код на сайте.")

# --- API ЭНДПОИНТЫ ---
@app.post("/request_code")
async def request_code():
    # Удаляем старые коды, чтобы не забивать память
    if len(pending_auths) > 50: pending_auths.clear()
    
    code = str(random.randint(100000, 999999))
    pending_auths[code] = None
    print(f"--- СГЕНЕРИРОВАН КОД: {code} ---")
    return {"code": code}

@app.get("/check_login/{code}")
async def check_login(code: str):
    if code in pending_auths and pending_auths[code] is not None:
        return {"status": "success", "username": pending_auths[code]["username"]}
    return {"status": "waiting"}

@app.get("/messages")
async def get_messages(me: str, with_user: str):
    with SessionLocal() as db:
        # Ищем сообщения только между тобой и конкретным человеком
        msgs = db.query(Message).filter(
            ((Message.sender == me) & (Message.receiver == with_user)) |
            ((Message.sender == with_user) & (Message.receiver == me))
        ).order_by(Message.timestamp).all()
        return [{"sender": m.sender, "text": m.text} for m in msgs]

@app.post("/send")
async def send_msg(sender: str, receiver: str, text: str):
    if not text.strip(): return {"status": "empty"}
    with SessionLocal() as db:
        new_msg = Message(sender=sender, receiver=receiver, text=text)
        db.add(new_msg)
        db.commit()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# Запуск бота в фоне при старте сервера
@app.on_event("startup")
async def startup():
    # ВАЖНО: удаляем все зависшие сообщения, чтобы избежать ConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
