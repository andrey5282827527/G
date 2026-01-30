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
DIRS = ["voice_files", "stickers", "uploads"]
for d in DIRS:
    if not os.path.exists(d): os.makedirs(d)

# --- БАЗА ДАННЫХ ---
class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    receiver = Column(String)
    text = Column(Text)
    msg_type = Column(String, default="text") # text, voice, sticker
    timestamp = Column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    owner = Column(String)
    room_type = Column(String, default="group")

class Sticker(Base):
    __tablename__ = "stickers"
    id = Column(Integer, primary_key=True)
    pack_name = Column(String)
    file_path = Column(String)

class StickerOwner(Base):
    __tablename__ = "sticker_owners"
    id = Column(Integer, primary_key=True)
    pack_name = Column(String, unique=True)
    username = Column(String)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()
pending_auths = {}

# --- ТЕЛЕГРАМ БОТ ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message()
async def handle_tg(message: types.Message):
    code = message.text.strip()
    if code in pending_auths:
        user = message.from_user.username or f"id{message.from_user.id}"
        pending_auths[code] = {"username": user}
        await message.answer(f"✅ Успешный вход, @{user}!")

# --- API ЭНДПОИНТЫ ---

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

@app.get("/list_rooms")
def list_rooms():
    with SessionLocal() as db:
        return [{"name": r.name, "type": r.room_type} for r in db.query(Room).all()]

@app.post("/create_room")
def create_room(name: str, owner: str):
    with SessionLocal() as db:
        if db.query(Room).filter(Room.name == name).first(): return {"error": "exists"}
        db.add(Room(name=name, owner=owner))
        db.commit()
    return {"ok": True}

@app.get("/messages")
def get_msgs(me: str, target: str):
    with SessionLocal() as db:
        # Авто-удаление старых ГС (старше 5 минут)
        limit = datetime.utcnow() - timedelta(minutes=5)
        old_voices = db.query(Message).filter(Message.msg_type == "voice", Message.timestamp < limit).all()
        for v in old_voices:
            if os.path.exists(v.text): os.remove(v.text)
            db.delete(v)
        db.commit()

        is_room = db.query(Room).filter(Room.name == target).first()
        if is_room:
            msgs = db.query(Message).filter(Message.receiver == target).all()
        else:
            msgs = db.query(Message).filter(or_(
                (Message.sender == me) & (Message.receiver == target),
                (Message.sender == target) & (Message.receiver == me)
            )).all()
        return [{"sender": m.sender, "text": m.text, "type": m.msg_type} for m in msgs]

@app.post("/send")
def send_text(sender: str, receiver: str, text: str):
    with SessionLocal() as db:
        db.add(Message(sender=sender, receiver=receiver, text=text, msg_type="text"))
        db.commit()
    return {"ok": True}

@app.post("/send_voice")
async def send_voice(sender: str, receiver: str, file: UploadFile = File(...)):
    path = f"voice_files/{random.randint(1000,9999)}.ogg"
    with open(path, "wb") as f: f.write(await file.read())
    with SessionLocal() as db:
        db.add(Message(sender=sender, receiver=receiver, text=path, msg_type="voice"))
        db.commit()
    return {"ok": True}

@app.get("/get_voice")
def get_v(path: str):
    if os.path.exists(path): return FileResponse(path)
    return {"error": "file not found"}

# --- СТИКЕРЫ С ЗАЩИТОЙ ---
@app.post("/create_sticker")
async def create_sticker(pack: str, owner: str, file: UploadFile = File(...)):
    with SessionLocal() as db:
        # Проверка владельца пака
        p_owner = db.query(StickerOwner).filter(StickerOwner.pack_name == pack).first()
        if p_owner:
            if p_owner.username != owner:
                return {"error": "Доступ запрещен! Пак принадлежит другому."}
        else:
            # Если пак новый, закрепляем его за тобой
            db.add(StickerOwner(pack_name=pack, username=owner))
        
        path = f"stickers/{pack}_{random.randint(1000,9999)}.png"
        with open(path, "wb") as f: f.write(await file.read())
        db.add(Sticker(pack_name=pack, file_path=path))
        db.commit()
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    return open("index.html", "r", encoding="utf-8").read()

@app.on_event("startup")
async def startup():
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
