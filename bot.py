import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from huggingface_hub import InferenceClient

# Пряник берет ключи из настроек сервера
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = InferenceClient(api_key=HF_TOKEN)

BAD_WORDS = ["хуй", "пизд", "ебл", "еба", "сук", "хуя", "бля", "урод"]

SYSTEM_PROMPT = (
    "Ты — дерзкий ИИ 'Тульский Пряник' канала TLPART. "
    "Если тебя матерят — ты материшь в ответ жестко. "
    "В остальное время ты умный и решаешь любые задачи."
)

@dp.message(F.text)
async def chat(message: types.Message):
    is_bad = any(word in message.text.lower() for word in BAD_WORDS)
    prompt = SYSTEM_PROMPT + ("\nЮЗЕР ТЕБЯ ОСКОРБИЛ! ОТВЕТЬ МАТОМ!" if is_bad else "")
    
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        out = client.chat_completion(
            model="Qwen/Qwen2.5-72B-Instruct",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": message.text}],
            max_tokens=800
        )
        ans = out.choices[0].message.content
        await message.reply(ans.replace("Qwen", "Тульский Пряник"))
    except:
        await message.answer("Я прилег, лимиты сдохли. Пиши через 5 минут.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
