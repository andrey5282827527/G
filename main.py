import os, random, uvicorn, time
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, or_
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- НАСТРОЙКИ ---
TOKEN = "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE"
WEBHOOK_URL = "https://g-15es.onrender.com/webhook"
UPLOAD_DIR = "./voice"
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

class Base(DeclarativeBase): pass
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String); receiver = Column(String)
    text = Column(Text); msg_type = Column(String, default="text") # text или voice
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
bot = Bot(token=TOKEN); dp = Dispatcher(); pending_auths = {}

# --- ЛОГИКА ОЧИСТКИ ---
def clean_old_voices():
    db = SessionLocal()
    # Удаляем записи старше 5 минут, если это voice
    limit = datetime.utcnow() - timedelta(minutes=5)
    old_voices = db.query(Message).filter(Message.msg_type == "voice", Message.timestamp < limit).all()
    for v in old_voices:
        if os.path.exists(v.text): os.remove(v.text)
        db.delete(v)
    db.commit(); db.close()

@app.get("/messages")
def get_history(me: str, with_user: str):
    clean_old_voices() # Чистим при каждом запросе
    db = SessionLocal()
    msgs = db.query(Message).filter(
        or_((Message.sender==me) & (Message.receiver==with_user),
            (Message.sender==with_user) & (Message.receiver==me))
    ).order_by(Message.timestamp).all()
    return [{"sender": m.sender, "text": m.text, "type": m.msg_type} for m in msgs]

@app.get("/my_chats")
def get_my_chats(me: str):
    db = SessionLocal()
    # Находим всех уникальных собеседников
    sent = db.query(Message.receiver).filter(Message.sender == me).distinct()
    received = db.query(Message.sender).filter(Message.receiver == me).distinct()
    chats = list(set([r[0] for r in sent] + [r[0] for r in received]))
    return chats

@app.post("/send_voice")
async def send_voice(sender: str, receiver: str, file: UploadFile = File(...)):
    fname = f"{UPLOAD_DIR}/{random.randint(1000,9999)}_{file.filename}"
    with open(fname, "wb") as f: f.write(await file.read())
    db = SessionLocal()
    db.add(Message(sender=sender, receiver=receiver, text=fname, msg_type="voice"))
    db.commit(); return {"ok": True}

@app.get("/get_voice")
def get_voice(path: str):
    return FileResponse(path)

# ... (остальные эндпоинты: /webhook, /request_code, /check_login как раньше) ...

@app.post("/send")
def send_msg(sender: str, receiver: str, text: str):
    db = SessionLocal(); db.add(Message(sender=sender, receiver=receiver, text=text)); db.commit(); return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index(): return open("index.html", encoding="utf-8").read()

@app.on_event("startup")
async def on_startup(): await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=10000)
