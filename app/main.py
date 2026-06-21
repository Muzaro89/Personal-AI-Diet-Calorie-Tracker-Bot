from contextlib import asynccontextmanager
from datetime import date
import re

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import (
    get_daily_totals,
    get_db,
    get_last_food_log,
    get_or_create_user,
    init_db,
    save_food_log,
    update_food_log,
)
from app.gemini_service import FoodAnalysisResult, analyze_food_image, recalculate_food_with_correction

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

CORRECTION_PATTERN = re.compile(
    r"^[+\-]|^\d+\s*g\b|tambah|kurang|koreksi|ganti|tanpa|extra|ekstra",
    re.IGNORECASE,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Telegram Calorie Tracker Bot",
    description="Backend webhook untuk bot Telegram pelacak kalori makanan",
    lifespan=lifespan,
)


async def send_telegram_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
        response.raise_for_status()


async def download_telegram_photo(file_id: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_response = await client.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id})
        file_response.raise_for_status()
        file_path = file_response.json()["result"]["file_path"]

        download_response = await client.get(
            f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        )
        download_response.raise_for_status()

        mime_type = "image/jpeg"
        if file_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif file_path.lower().endswith(".webp"):
            mime_type = "image/webp"

        return download_response.content, mime_type


def format_food_result(result: FoodAnalysisResult) -> str:
    return (
        f"🍽 <b>{result.food_name}</b>\n\n"
        f"🔥 Kalori: {result.calories:.0f} kcal\n"
        f"🥩 Protein: {result.protein:.1f} g\n"
        f"🍞 Karbo: {result.carbs:.1f} g\n"
        f"🧈 Lemak: {result.fat:.1f} g"
    )


def format_daily_summary(totals: dict[str, float | int], target_date: date) -> str:
    if totals["count"] == 0:
        return f"Belum ada log makanan untuk tanggal {target_date.isoformat()}."

    return (
        f"📊 <b>Ringkasan {target_date.isoformat()}</b>\n\n"
        f"🍱 Jumlah makanan: {totals['count']}\n"
        f"🔥 Total kalori: {totals['calories']:.0f} kcal\n"
        f"🥩 Protein: {totals['protein']:.1f} g\n"
        f"🍞 Karbo: {totals['carbs']:.1f} g\n"
        f"🧈 Lemak: {totals['fat']:.1f} g"
    )


def format_photo_reply(result: FoodAnalysisResult, totals: dict[str, float | int]) -> str:
    return (
        f"{format_food_result(result)}\n\n"
        f"✅ Tersimpan ke log harian.\n\n"
        f"📊 <b>Total kalori hari ini: {totals['calories']:.0f} kcal</b>"
    )


def format_correction_reply(result: FoodAnalysisResult, totals: dict[str, float | int]) -> str:
    return (
        f"✏️ <b>Koreksi diterapkan</b>\n\n"
        f"{format_food_result(result)}\n\n"
        f"📊 <b>Total kalori hari ini: {totals['calories']:.0f} kcal</b>"
    )


def is_correction_message(text: str) -> bool:
    if not text or text.startswith("/"):
        return False
    return bool(CORRECTION_PATTERN.search(text))


def food_log_to_result(food_log) -> FoodAnalysisResult:
    return FoodAnalysisResult(
        food_name=food_log.food_name,
        calories=food_log.calories,
        protein=food_log.protein,
        carbs=food_log.carbs,
        fat=food_log.fat,
    )


async def handle_text_message(chat_id: int, text: str, db: Session, user) -> None:
    if text.startswith("/start"):
        await send_telegram_message(
            chat_id,
            "Halo! Kirim foto makanan untuk dianalisis.\n\n"
            "Perintah:\n"
            "/today — ringkasan makanan hari ini\n\n"
            "Koreksi:\n"
            "Kirim teks seperti <code>+100g nasi</code> untuk menyesuaikan log terakhir.",
        )
        return

    if text.startswith("/today"):
        totals = get_daily_totals(db, user.id, date.today())
        await send_telegram_message(chat_id, format_daily_summary(totals, date.today()))
        return

    if is_correction_message(text):
        await handle_correction_message(chat_id, text, db, user)
        return

    await send_telegram_message(
        chat_id,
        "Kirim foto makanan agar saya bisa menganalisis kalorinya.\n"
        "Ketik /today untuk ringkasan, atau kirim koreksi seperti <code>+100g nasi</code>.",
    )


async def handle_correction_message(chat_id: int, text: str, db: Session, user) -> None:
    last_log = get_last_food_log(db, user.id, log_date=date.today())
    if last_log is None:
        await send_telegram_message(
            chat_id,
            "Belum ada log makanan hari ini untuk dikoreksi. Kirim foto makanan dulu.",
        )
        return

    await send_telegram_message(chat_id, "⏳ Menghitung ulang berdasarkan koreksi...")

    previous = food_log_to_result(last_log)
    result = await recalculate_food_with_correction(previous, text)

    update_food_log(
        db,
        last_log,
        food_name=result.food_name,
        calories=result.calories,
        protein=result.protein,
        carbs=result.carbs,
        fat=result.fat,
    )

    totals = get_daily_totals(db, user.id, date.today())
    await send_telegram_message(chat_id, format_correction_reply(result, totals))


async def handle_photo_message(chat_id: int, photos: list, db: Session, user) -> None:
    await send_telegram_message(chat_id, "⏳ Menganalisis foto makanan...")

    file_id = photos[-1]["file_id"]
    image_bytes, mime_type = await download_telegram_photo(file_id)
    result = await analyze_food_image(image_bytes, mime_type)

    save_food_log(
        db,
        user_id=user.id,
        food_name=result.food_name,
        calories=result.calories,
        protein=result.protein,
        carbs=result.carbs,
        fat=result.fat,
        log_date=date.today(),
    )

    totals = get_daily_totals(db, user.id, date.today())
    await send_telegram_message(chat_id, format_photo_reply(result, totals))


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
 #   if settings.webhook_secret:
 #       secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
 #       if secret != settings.webhook_secret:
 #           raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    telegram_id = from_user.get("id")
    if telegram_id is None:
        return {"ok": True}

    user = get_or_create_user(db, telegram_id, from_user.get("username"))
    text = (message.get("text") or "").strip()
    photos = message.get("photo")

    try:
        if photos:
            await handle_photo_message(chat_id, photos, db, user)
        elif text:
            await handle_text_message(chat_id, text, db, user)
        else:
            await send_telegram_message(
                chat_id,
                "Kirim foto makanan atau ketik /today untuk ringkasan harian.",
            )
    except Exception as exc:
        await send_telegram_message(chat_id, f"❌ Terjadi kesalahan: {exc}")

    return {"ok": True}
