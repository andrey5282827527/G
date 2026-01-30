import os, random, uvicorn
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
for d in ["voice_files", "stickers"]:
    if not os.path.exists(d): os.makedirs(d)

class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String); receiver = Column(String)
    text = Column(Text); msg_type = Column(String, default="text")
    timestamp = Column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True); owner = Column(String)

class StickerOwner(Base):
    __tablename__ = "sticker_owners"
    id = Column(Integer, primary_key=True)
    pack_name = Column(String, unique=True); username = Column(String)

engine = create_engine("sqlite:///./messenger.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()
bot = Bot(token=TOKEN); dp = Dispatcher(); pending_auths = {}

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
        await message.answer(f"✅ Вход разрешен, @{user}!")

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

@app.get("/get_my_chats")
def get_my_chats(me: str):
    with SessionLocal() as db:
        rooms = [{"name": r.name, "type": "group"} for r in db.query(Room).all()]
        # Находим всех, с кем есть сообщения
        sent = db.query(Message.receiver).filter(Message.sender == me).distinct().all()
        recd = db.query(Message.sender).filter(Message.receiver == me).distinct().all()
        u_names = list(set([r[0] for r in sent] + [r[0] for r in recd]))
        room_names = [r["name"] for r in rooms]
        privates = [{"name": u, "type": "private"} for u in u_names if u not in room_names and u != me]
        return rooms + privates

@app.get("/messages")
def get_msgs(me: str, target: str):
    with SessionLocal() as db:
        # Чистка ГС (5 мин)
        limit = datetime.utcnow() - timedelta(minutes=5)
        old = db.query(Message).filter(Message.msg_type == "voice", Message.timestamp < limit).all()
        for v in old:
            if os.path.exists(v.text): os.remove(v.text); db.delete(v)
        db.commit()
        
        is_room = db.query(Room).filter(Room.name == target).first()
        if is_room:
            msgs = db.query(Message).filter(Message.receiver == target).all()
        else:
            msgs = db.query(Message).filter(or_((Message.sender==me)&(Message.receiver==target), (Message.sender==target)&(Message.receiver==me))).all()
        return [{"sender": m.sender, "text": m.text, "type": m.msg_type} for m in msgs]

@app.post("/send")
def send_msg(sender: str, receiver: str, text: str):
    with SessionLocal() as db:
        db.add(Message(sender=sender, receiver=receiver, text=text))
        db.commit()
    return {"ok": True}

@app.post("/create_room")
def create_room(name: str, owner: str):
    with SessionLocal() as db:
        if not db.query(Room).filter(Room.name == name).first():
            db.add(Room(name=name, owner=owner))
            db.commit()
    return {"ok": True}

@app.post("/create_sticker")
async def create_sticker(pack: str, owner: str, file: UploadFile = File(...)):
    with SessionLocal() as db:
        p_owner = db.query(StickerOwner).filter(StickerOwner.pack_name == pack).first()
        if p_owner and p_owner.username != owner: return {"error": "denied"}
        if not p_owner: db.add(StickerOwner(pack_name=pack, username=owner))
        path = f"stickers/{pack}_{random.randint(100,999)}.png"
        with open(path, "wb") as f: f.write(await file.read())
        db.add(Message(sender=owner, receiver=pack, text=path, msg_type="sticker_def")) # просто храним путь
        db.commit()
    return {"ok": True}

@app.get("/get_voice")
def get_v(path: str): return FileResponse(path) if os.path.exists(path) else {"err":404}

@app.get("/", response_class=HTMLResponse)
def index(): return open("index.html", "r", encoding="utf-8").read()

@app.on_event("startup")
async def startup(): await bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=10000)
