import os
import random
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
from email.message import EmailMessage
import aiosmtplib

# Теперь программа берет данные из настроек сервера, а не из текста
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
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
temp_codes = {}

# --- ПОЧТА ---
async def send_mail(target_email: str, code: str):
    msg = EmailMessage()
    msg.set_content(f"Твой код входа: {code}")
    msg["Subject"] = "Mini-Gram Code"
    msg["From"] = SENDER_EMAIL
    msg["To"] = target_email
    try:
        await aiosmtplib.send(msg, hostname="smtp.mail.ru", port=465, 
                              username=SENDER_EMAIL, password=SENDER_PASSWORD, use_tls=True)
    except Exception as e:
        print(f"Ошибка почты: {e}")

# --- API ЭНДПОИНТЫ ---
@app.post("/get_code")
async def get_code(email: str, background_tasks: BackgroundTasks):
    code = str(random.randint(1000, 9999))
    temp_codes[email] = code
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
        return {"username": username}
    raise HTTPException(status_code=400, detail="Wrong code")

@app.get("/messages")
async def get_messages():
    with SessionLocal() as db:
        return db.query(Message).order_by(Message.timestamp.desc()).limit(50).all()

@app.post("/send")
async def send_msg(username: str, text: str):
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
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

