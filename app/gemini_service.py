import json
import re

import google.generativeai as genai
from pydantic import BaseModel, Field

from app.config import settings

genai.configure(api_key=settings.gemini_api_key)

ANALYSIS_PROMPT = """Analisis foto makanan ini dan estimasi nilai gizi.
Balas HANYA dengan JSON valid (tanpa markdown, tanpa penjelasan) dengan format:
{
  "food_name": "nama makanan dalam Bahasa Indonesia",
  "calories": angka_kalori_kcal,
  "protein": gram_protein,
  "carbs": gram_karbohidrat,
  "fat": gram_lemak
}
"""


class FoodAnalysisResult(BaseModel):
    food_name: str = Field(description="Nama makanan")
    calories: float = Field(ge=0, description="Kalori (kcal)")
    protein: float = Field(ge=0, description="Protein (gram)")
    carbs: float = Field(ge=0, description="Karbohidrat (gram)")
    fat: float = Field(ge=0, description="Lemak (gram)")


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


async def analyze_food_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> FoodAnalysisResult:
    model = genai.GenerativeModel(settings.gemini_model)

    response = model.generate_content(
        [
            ANALYSIS_PROMPT,
            {"mime_type": mime_type, "data": image_bytes},
        ],
        generation_config={"response_mime_type": "application/json"},
    )

    raw_text = response.text or ""
    if not raw_text.strip():
        raise ValueError("Gemini tidak mengembalikan respons analisis makanan.")

    data = _extract_json(raw_text)
    return FoodAnalysisResult.model_validate(data)
