import os
import logging
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram import F
import asyncio
import easyocr
from PIL import Image
from io import BytesIO
import aiohttp

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "0"))
ALLOWED_USERS = {OWNER_USER_ID}

# Инициализация EasyOCR (загрузка моделей — происходит один раз при запуске)
logging.info("Загружаю EasyOCR для русского и английского языков...")
reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
logging.info("EasyOCR готов к работе!")

# Простой фильтр мата (защита)
MAT_WORDS = [
    "бля", "блять", "блядь", "пизд", "хуй", "хуи", "хуе", "хуё", "хуя", "хую", "хрен", "хуило",
    "сука", "суч", "еба", "ёба", "еби", "ёби", "ебу", "ёбу", "ебё", "ёбё", "нахуй", "нахуя",
    "пидор", "педик", "гандон", "вагина", "хер", "дроч", "мудак", "говно", "залуп", "жопа",
    "трах", "ебал", "ебан", "fuck", "bitch", "shit", "cock", "dick", "pussy", "whore"
]

def has_mat(text: str) -> bool:
    if not text:
        return False
    clean = text.lower().replace("*", "").replace("0", "о").replace("3", "е").replace("ё", "е").replace(" ", "")
    return any(word in clean for word in MAT_WORDS)

# ============ СЕРВИСЫ ============
async def download_file(bot, file_id: str) -> BytesIO:
    """Скачать файл из Telegram в память"""
    file = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            content = await resp.read()
            return BytesIO(content)

async def ocr_image_easy(image_bytes: BytesIO) -> str:
    """Распознавание текста через EasyOCR (локально, без интернета)"""
    try:
        image = Image.open(image_bytes)
        results = reader.readtext(image)
        text = " ".join([res[1] for res in results])
        text = text.strip()
        
        if not text or len(text) < 3:
            return "❓ Не удалось распознать текст. Попробуй сфоткать чётче и при хорошем свете!"
        
        return text
    except Exception as e:
        logging.error(f"EasyOCR error: {e}")
        return "⚠️ Ошибка распознавания. Попробуй ещё раз или напиши текстом."

# ============ БОТ ============
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ALLOWED_USERS:
        await message.answer("🚫 У тебя нет доступа к этому боту.\nЭто персональный помощник для помощи с учёбой.")
        return
    
    kb = [
        [types.KeyboardButton(text="📚 Математика"), types.KeyboardButton(text="✍️ Русский язык")],
        [types.KeyboardButton(text="🌍 Английский"), types.KeyboardButton(text="📖 Литература")],
        [types.KeyboardButton(text="🔬 Биология"), types.KeyboardButton(text="🗺️ География")],
        [types.KeyboardButton(text="📸 Прислать фото задания")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "🌸 Привет! Я — умная подружка для помощи с уроками!\n\n"
        "✨ Просто пришли фото задачи из учебника — я распознаю текст и помогу разобрать шаг за шагом!\n\n"
        "<b>Важно:</b> Я не решаю за тебя — только объясню, как решить самой 😊",
        reply_markup=keyboard
    )

@dp.message(Command("помощь"))
async def help_cmd(message: types.Message):
    if message.from_user.id not in ALLOWED_USERS:
        return
    await message.answer(
        "<b>📚 Как пользоваться:</b>\n\n"
        "1️⃣ <b>Фото задания</b>\n   Просто пришли фото задачи из учебника — я распознаю текст и помогу разобрать.\n\n"
        "2️⃣ <b>Название предмета</b>\n   Напиши «математика», «русский» и т.д. — дам подсказку по теме.\n\n"
        "3️⃣ <b>Вопрос</b>\n   Задай вопрос — я объясню правило, а не дам готовый ответ.\n\n"
        "<b>🔒 Безопасность:</b>\n"
        "• Никакого мата и 18+ контента\n"
        "• Только педагогическая помощь"
    )

@dp.message(Command("разрешить"))
async def allow(message: types.Message):
    if message.from_user.id != OWNER_USER_ID:
        await message.answer("❌ Эта команда только для владельца бота.")
        return
    
    text = message.text.split()
    if len(text) < 3:
        await message.answer(
            "ℹ️ Использование:\n<code>/разрешить 123456789 Анна</code>\n\n"
            "Где 123456789 — user_id человека (узнать через @userinfobot)"
        )
        return
    
    try:
        new_user_id = int(text[1])
        name = text[2]
        ALLOWED_USERS.add(new_user_id)
        await message.answer(f"✅ {name} добавлена! Теперь она может писать боту.")
        try:
            await bot.send_message(new_user_id, f"🎉 Привет, {name}! Теперь я могу помогать тебе с уроками. Напиши /start")
        except:
            pass
    except:
        await message.answer("❌ Ошибка. Пример: <code>/разрешить 123456789 Анна</code>")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ALLOWED_USERS:
        return
    
    await message.answer("🔍 Распознаю текст на фото... (5-10 секунд)")
    
    # Скачиваем фото
    photo = message.photo[-1]  # самое большое фото
    image_bytes = await download_file(bot, photo.file_id)
    
    # Распознаём текст через EasyOCR
    text = await ocr_image_easy(image_bytes)
    
    # Проверка мата в распознанном тексте
    if has_mat(text):
        await message.answer("Давай общаться уважительно! Я здесь, чтобы помочь с учёбой 🌸")
        return
    
    # Анализируем предмет по ключевым словам
    text_lower = text.lower()
    subject_hint = ""
    
    if any(word in text_lower for word in ["уравнен", "решить", "х=", "корень", "дробь", "процент", "задача"]):
        subject_hint = "\n\n💡 Похоже на <b>математику</b>. Напиши «математика», и я объясню, как решать такие задачи!"
    elif any(word in text_lower for word in ["морф", "разбор", "причаст", "деепричаст", "орфограмм", "пунктуац", "правописан"]):
        subject_hint = "\n\n💡 Похоже на <b>русский язык</b>. Напиши «русский», и я напомню правило!"
    elif any(word in text_lower for word in ["перевед", "английск", "слов", "предложен", "translate"]):
        subject_hint = "\n\n💡 Похоже на <b>английский</b>. Напиши «английский», и я помогу с переводом!"
    
    await message.answer(
        f"📄 Распознанный текст:\n\n<pre>{text}</pre>\n\n"
        f"✨ Теперь я могу:\n"
        f"• Объяснить правило по этому заданию\n"
        f"• Дать подсказку для решения шаг за шагом{subject_hint}\n\n"
        f"<i>Напиши название предмета или задай вопрос по тексту!</i>",
        parse_mode="HTML"
    )

@dp.message(F.text)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ALLOWED_USERS:
        return
    
    # Проверка мата
    if has_mat(message.text):
        await message.answer("Давай общаться уважительно! Я здесь, чтобы помочь с учёбой 🌸")
        return
    
    text_lower = message.text.lower()
    
    # Обработка кнопок и предметов
    if "математика" in text_lower:
        await message.answer(
            "📐 <b>Математика</b>\n\n"
            "Напиши задачу или уравнение — я помогу разобрать по шагам!\n\n"
            "Пример:\n"
            "<i>Реши уравнение: 2x + 5 = 15</i>\n\n"
            "⚠️ Я не дам готовый ответ сразу — сначала подскажу, как решить самой 😊"
        )
    elif "русский" in text_lower or "язык" in text_lower:
        await message.answer(
            "✍️ <b>Русский язык</b>\n\n"
            "Пришли предложение для проверки или задание по правилам — объясню без ошибок!\n\n"
            "Пример:\n"
            "<i>Проверь: мы пошли в магазин за хлебом</i>"
        )
    elif "английский" in text_lower:
        await message.answer(
            "🌍 <b>Английский</b>\n\n"
            "Напиши слово для перевода или предложение для разбора — помогу понять грамматику!\n\n"
            "Пример:\n"
            "<i>Переведи: I am going to school</i>"
        )
    elif "литература" in text_lower:
        await message.answer(
            "📖 <b>Литература</b>\n\n"
            "Спроси о произведении, герое или теме — помогу с анализом и цитатами!\n\n"
            "Пример:\n"
            "<i>Кто такой Печорин в «Герое нашего времени»?</i>"
        )
    elif "биологи" in text_lower:
        await message.answer(
            "🌱 <b>Биология</b>\n\n"
            "Спроси о растениях, животных или процессах в природе!\n\n"
            "Пример:\n"
            "<i>Что такое фотосинтез?</i>"
        )
    elif "географи" in text_lower:
        await message.answer(
            "🗺️ <b>География</b>\n\n"
            "Спроси о странах, климате или картах!\n\n"
            "Пример:\n"
            "<i>Что такое умеренный климат?</i>"
        )
    elif "📸 прислать фото задания" in text_lower:
        await message.answer("📱 Просто пришли фото задачи из учебника — я распознаю текст и помогу разобрать!")
    else:
        await message.answer(
            f"💬 Получила: «{message.text}»\n\n"
            "Чтобы я помогла:\n"
            "• Напиши предмет (математика, русский...)\n"
            "• Или пришли фото задания 📸\n"
            "• Или /помощь для инструкции"
        )

async def main():
    if not BOT_TOKEN or OWNER_USER_ID == 0:
        print("❌ ОШИБКА: Не заполнен файл .env!")
        print("\nСоздай файл .env в папке school_bot со строками:")
        print("BOT_TOKEN=твой_токен_от_BotFather")
        print("OWNER_USER_ID=твой_user_id")
        return
    
    print(f"\n✅ Бот запущен!")
    print(f"   Владелец: {OWNER_USER_ID}")
    print(f"   Разрешённые пользователи: {len(ALLOWED_USERS)}")
    print(f"   OCR (распознавание фото): ✅ EasyOCR готов")
    print("\n💬 Открой Telegram и напиши боту /start")
    print("   Пришли фото задачи — я распознаю текст! 📸✨\n")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
