from contextlib import asynccontextmanager
from datetime import date

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.gemini_service import analyze_food_image
from app.models import FoodLog, User

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


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


def get_or_create_user(db: Session, telegram_id: int, username: str | None) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif username and user.username != username:
        user.username = username
        db.commit()
    return user


def format_food_result(result) -> str:
    return (
        f"🍽 <b>{result.food_name}</b>\n\n"
        f"🔥 Kalori: {result.calories:.0f} kcal\n"
        f"🥩 Protein: {result.protein:.1f} g\n"
        f"🍞 Karbo: {result.carbs:.1f} g\n"
        f"🧈 Lemak: {result.fat:.1f} g"
    )


def format_daily_summary(db: Session, user: User, target_date: date) -> str:
    totals = (
        db.query(
            func.count(FoodLog.id),
            func.coalesce(func.sum(FoodLog.calories), 0),
            func.coalesce(func.sum(FoodLog.protein), 0),
            func.coalesce(func.sum(FoodLog.carbs), 0),
            func.coalesce(func.sum(FoodLog.fat), 0),
        )
        .filter(FoodLog.user_id == user.id, FoodLog.log_date == target_date)
        .one()
    )

    count, calories, protein, carbs, fat = totals
    if count == 0:
        return f"Belum ada log makanan untuk tanggal {target_date.isoformat()}."

    return (
        f"📊 <b>Ringkasan {target_date.isoformat()}</b>\n\n"
        f"🍱 Jumlah makanan: {count}\n"
        f"🔥 Total kalori: {calories:.0f} kcal\n"
        f"🥩 Protein: {protein:.1f} g\n"
        f"🍞 Karbo: {carbs:.1f} g\n"
        f"🧈 Lemak: {fat:.1f} g"
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/webhook/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if settings.webhook_secret and secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    telegram_id = from_user.get("id")
    if telegram_id is None:
        return {"ok": True}

    text = (message.get("text") or "").strip()
    user = get_or_create_user(db, telegram_id, from_user.get("username"))

    if text.startswith("/start"):
        await send_telegram_message(
            chat_id,
            "Halo! Kirim foto makanan untuk dianalisis.\n\n"
            "Perintah:\n"
            "/today — ringkasan makanan hari ini",
        )
        return {"ok": True}

    if text.startswith("/today"):
        summary = format_daily_summary(db, user, date.today())
        await send_telegram_message(chat_id, summary)
        return {"ok": True}

    photos = message.get("photo")
    if not photos:
        await send_telegram_message(
            chat_id,
            "Kirim foto makanan agar saya bisa menganalisis kalorinya.",
        )
        return {"ok": True}

    try:
        await send_telegram_message(chat_id, "⏳ Menganalisis foto makanan...")

        file_id = photos[-1]["file_id"]
        image_bytes, mime_type = await download_telegram_photo(file_id)
        result = await analyze_food_image(image_bytes, mime_type)

        food_log = FoodLog(
            user_id=user.id,
            food_name=result.food_name,
            calories=result.calories,
            protein=result.protein,
            carbs=result.carbs,
            fat=result.fat,
            log_date=date.today(),
        )
        db.add(food_log)
        db.commit()

        await send_telegram_message(
            chat_id,
            format_food_result(result) + "\n\n✅ Tersimpan ke log harian.",
        )
    except Exception as exc:
        await send_telegram_message(
            chat_id,
            f"❌ Gagal menganalisis foto: {exc}",
        )

    return {"ok": True}
