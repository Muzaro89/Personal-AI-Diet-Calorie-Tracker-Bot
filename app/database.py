from collections.abc import Generator
from datetime import date

from sqlalchemy import create_engine, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_or_create_user(db: Session, telegram_id: int, username: str | None):
    from app.models import User

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


def save_food_log(
    db: Session,
    *,
    user_id: int,
    food_name: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
    log_date: date,
):
    from app.models import FoodLog

    food_log = FoodLog(
        user_id=user_id,
        food_name=food_name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        log_date=log_date,
    )
    db.add(food_log)
    db.commit()
    db.refresh(food_log)
    return food_log


def get_daily_totals(db: Session, user_id: int, target_date: date) -> dict[str, float | int]:
    from app.models import FoodLog

    count, calories, protein, carbs, fat = (
        db.query(
            func.count(FoodLog.id),
            func.coalesce(func.sum(FoodLog.calories), 0),
            func.coalesce(func.sum(FoodLog.protein), 0),
            func.coalesce(func.sum(FoodLog.carbs), 0),
            func.coalesce(func.sum(FoodLog.fat), 0),
        )
        .filter(FoodLog.user_id == user_id, FoodLog.log_date == target_date)
        .one()
    )

    return {
        "count": int(count),
        "calories": float(calories),
        "protein": float(protein),
        "carbs": float(carbs),
        "fat": float(fat),
    }


def get_last_food_log(db: Session, user_id: int, log_date: date | None = None):
    from app.models import FoodLog

    query = db.query(FoodLog).filter(FoodLog.user_id == user_id)
    if log_date is not None:
        query = query.filter(FoodLog.log_date == log_date)

    return query.order_by(FoodLog.logged_at.desc(), FoodLog.id.desc()).first()


def update_food_log(
    db: Session,
    food_log,
    *,
    food_name: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
):
    food_log.food_name = food_name
    food_log.calories = calories
    food_log.protein = protein
    food_log.carbs = carbs
    food_log.fat = fat
    db.commit()
    db.refresh(food_log)
    return food_log
