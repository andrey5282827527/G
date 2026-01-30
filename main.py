import os, random, uvicorn, shutil
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
VOICE_DIR = "voice_files"
if not os.path.exists(VOICE_DIR): os.makedirs(VOICE_DIR)

# --- БД ---
class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    receiver = Column(String) # Ник юзера или ID группы/канала
    text = Column(Text)
    msg_type = Column(String, default="text") # text, voice
    timestamp = Column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    owner = Column(String)
    room_type = Column(String) # group, channel

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
bot = Bot(token=TOKEN); dp = Dispatcher(); pending_auths = {}

# --- API ---
@app.get("/messages")
def get_msgs(me: str, target: str):
    db = SessionLocal()
    # Чистка старых ГС (удаляем файлы старше 5 мин)
    old = db.query(Message).filter(Message.msg_type=="voice", Message.timestamp < datetime.utcnow()-timedelta(minutes=5)).all()
    for o in old:
        if os.path.exists(o.text): os.remove(o.text)
        db.delete(o)
    db.commit()

    # Запрос истории (личка или группа)
    is_room = db.query(Room).filter(Room.name == target).first()
    if is_room:
        msgs = db.query(Message).filter(Message.receiver == target).order_by(Message.timestamp).all()
    else:
        msgs = db.query(Message).filter(or_(
            (Message.sender==me) & (Message.receiver==target),
            (Message.sender==target) & (Message.receiver==me)
        )).order_by(Message.timestamp).all()
    return [{"sender": m.sender, "text": m.text, "type": m.msg_type} for m in msgs]

@app.post("/create_room")
def create_room(name: str, owner: str, rtype: str):
    db = SessionLocal()
    if db.query(Room).filter(Room.name == name).first(): return {"status":"exists"}
    db.add(Room(name=name, owner=owner, room_type=rtype))
    db.commit()
    return {"status":"ok"}

@app.get("/list_rooms")
def list_rooms():
    db = SessionLocal()
    return [{"name": r.name, "type": r.room_type} for r in db.query(Room).all()]

@app.post("/send_voice")
async def save_voice(sender: str, receiver: str, file: UploadFile = File(...)):
    path = f"{VOICE_DIR}/{random.randint(100,999)}_{file.filename}.ogg"
    with open(path, "wb") as f: f.write(await file.read())
    db = SessionLocal()
    db.add(Message(sender=sender, receiver=receiver, text=path, msg_type="voice"))
    db.commit()
    return {"ok": True}

@app.get("/get_voice")
def get_v(path: str): return FileResponse(path)

# (Остальные стандартные функции /webhook, /request_code сохраняются из прошлого кода)
@app.post("/send")
def send_msg(sender: str, receiver: str, text: str):
    db = SessionLocal(); db.add(Message(sender=sender, receiver=receiver, text=text)); db.commit(); return {"ok":True}

@app.get("/", response_class=HTMLResponse)
def index(): return open("index.html", encoding="utf-8").read()

@app.on_event("startup")
async def on_startup(): await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=10000)
