import os
import random
import asyncio
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
from email.message import EmailMessage
import aiosmtplib

# --- НАСТРОЙКИ ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# --- БАЗА ДАННЫХ ---
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    username = Column(String, unique=True)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.all_all = Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
temp_codes = {}

# --- ОТПРАВКА ПОЧТЫ С ЛОГИРОВАНИЕМ ---
async def send_mail(target_email: str, code: str):
    print(f"\n>>> ПОПЫТКА ОТПРАВКИ КОДА НА {target_email}...")
    
    msg = EmailMessage()
    msg.set_content(f"Твой код для входа: {code}")
    msg["Subject"] = "Код подтверждения Mini-Gram"
    msg["From"] = SENDER_EMAIL
    msg["To"] = target_email
    
    try:
        # Пробуем порт 587 (наиболее вероятный для Render)
        await aiosmtplib.send(
            msg, 
            hostname="smtp.mail.ru", 
            port=587, 
            username=SENDER_EMAIL, 
            password=SENDER_PASSWORD, 
            use_tls=False, 
            start_tls=True,
            timeout=10
        )
        print(f">>> [УСПЕХ] Код {code} удачно отправлен на почту {target_email}!")
    except Exception as e:
        print(f">>> [ОШИБКА] Код не ушел по почте. Причина: {e}")
        print(f">>> [ИНФО] Используй код из этой консоли для входа: {code}")

# --- API ---
@app.post("/get_code")
async def get_code(email: str, background_tasks: BackgroundTasks):
    code = str(random.randint(1000, 9999))
    temp_codes[email] = code
    # Код в любом случае пишем в консоль для админа
    print(f"\n--- ГЕНЕРАЦИЯ КОДА ---")
    print(f"ПОЛЬЗОВАТЕЛЬ: {email}")
    print(f"КОД: {code}")
    print(f"----------------------\n")
    
    background_tasks.add_task(send_mail, email, code)
    return {"status": "sent"}

@app.post("/login")
async def login(email: str, code: str, username: str):
    if temp_codes.get(email) == code:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email, username=username)
                db.add(user)
                db.commit()
        print(f">>> Юзер @{username} успешно вошел в систему.")
        return {"username": username}
    print(f">>> Ошибка входа: неверный код для {email}")
    raise HTTPException(status_code=400, detail="Неверный код")

@app.get("/messages")
async def get_messages():
    with SessionLocal() as db:
        msgs = db.query(Message).order_by(Message.timestamp.desc()).limit(50).all()
        return [{"sender": m.sender, "text": m.text} for m in reversed(msgs)]

@app.post("/send")
async def send_msg(username: str, text: str):
    if not text.strip(): return {"status": "empty"}
    with SessionLocal() as db:
        new_msg = Message(sender=username, text=text)
        db.add(new_msg)
        db.commit()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
