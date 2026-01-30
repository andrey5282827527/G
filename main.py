import os, random, uvicorn
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, or_, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from datetime import datetime

# Настройки
TOKEN = "8438399268:AAFfQ7ACMJFQ9PwRSv45SmSXWQQ6gF5CptE"
UPLOAD_DIR = "uploads"
for d in [UPLOAD_DIR, "voice_files", "stickers"]:
    if not os.path.exists(d): os.makedirs(d)

class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String); receiver = Column(String)
    text = Column(Text); msg_type = Column(String, default="text") # text, voice, sticker
    timestamp = Column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True); owner = Column(String)

class RoomMember(Base):
    __tablename__ = "room_members"
    id = Column(Integer, primary_key=True)
    room_name = Column(String); username = Column(String)

class Reaction(Base):
    __tablename__ = "reactions"
    id = Column(Integer, primary_key=True)
    msg_id = Column(Integer); emoji = Column(String); user = Column(String)

class Sticker(Base):
    __tablename__ = "stickers"
    id = Column(Integer, primary_key=True)
    pack_name = Column(String); file_path = Column(String)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()

# --- ЛИЧНЫЕ ЧАТЫ И ГРУППЫ ---
@app.get("/my_contacts")
def get_contacts(me: str):
    with SessionLocal() as db:
        # Получаем всех, с кем была переписка + группы, где состоишь
        rooms = [r.room_name for r in db.query(RoomMember).filter(RoomMember.username == me).all()]
        directs = db.query(Message.sender, Message.receiver).filter(or_(Message.sender == me, Message.receiver == me)).all()
        users = set()
        for s, r in directs:
            users.add(s if s != me else r)
        return {"users": list(users), "rooms": rooms}

@app.post("/add_to_group")
def add_to_group(room: str, target_user: str, admin: str):
    with SessionLocal() as db:
        room_obj = db.query(Room).filter(Room.name == room, Room.owner == admin).first()
        if not room_obj: return {"error": "Только админ может добавлять!"}
        db.add(RoomMember(room_name=room, username=target_user))
        db.commit()
    return {"ok": True}

# --- СТИКЕРЫ ---
@app.post("/create_sticker")
async def create_sticker(pack: str, file: UploadFile = File(...)):
    path = f"stickers/{pack}_{random.randint(1000,9999)}_{file.filename}"
    with open(path, "wb") as f: f.write(await file.read())
    with SessionLocal() as db:
        db.add(Sticker(pack_name=pack, file_path=path))
        db.commit()
    return {"ok": True}

@app.get("/get_stickers/{pack}")
def get_stickers(pack: str):
    with SessionLocal() as db:
        return [s.file_path for s in db.query(Sticker).filter(Sticker.pack_name == pack).all()]

# (Стандартные методы /messages, /send, /send_voice остаются из предыдущего кода)
# Добавляем реакции к /messages
@app.post("/react")
def react(msg_id: int, emoji: str, user: str):
    with SessionLocal() as db:
        db.add(Reaction(msg_id=msg_id, emoji=emoji, user=user))
        db.commit()
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index(): return open("index.html", "r", encoding="utf-8").read()
