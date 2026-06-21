import json

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import BaseModel, Field

from app.config import settings

genai.configure(api_key=settings.gemini_api_key)

GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = """Kamu adalah asisten analisis nutrisi makanan. Tugasmu HANYA menganalisis foto makanan dan mengembalikan estimasi nilai gizi.

ATURAN WAJIB:
1. Balas HANYA dengan satu objek JSON valid. Tanpa markdown, tanpa code fence, tanpa teks sebelum atau sesudah JSON.
2. Gunakan PERSIS struktur berikut (jangan tambah atau ubah nama field):
   {"food_name": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0}
3. food_name: string, nama makanan dalam Bahasa Indonesia (singkat dan spesifik).
4. calories: number, estimasi kalori total dalam kcal (bilangan bulat atau desimal).
5. protein, carbs, fat: number, estimasi dalam gram (bilangan bulat atau desimal).
6. Semua angka harus >= 0. Jangan gunakan null, string angka, atau satuan (g/kcal) di dalam nilai numerik.
7. Jika foto tidak jelas atau bukan makanan, tetap kembalikan JSON dengan food_name "Tidak dapat diidentifikasi" dan semua nilai numerik 0.
8. Estimasi harus realistis berdasarkan porsi yang terlihat di foto."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "food_name": {"type": "string"},
        "calories": {"type": "number"},
        "protein": {"type": "number"},
        "carbs": {"type": "number"},
        "fat": {"type": "number"},
    },
    "required": ["food_name", "calories", "protein", "carbs", "fat"],
}

USER_PROMPT = "Analisis foto makanan ini dan kembalikan estimasi nutrisi sesuai format JSON yang ditentukan."


class FoodAnalysisResult(BaseModel):
    food_name: str = Field(description="Nama makanan")
    calories: float = Field(ge=0, description="Kalori (kcal)")
    protein: float = Field(ge=0, description="Protein (gram)")
    carbs: float = Field(ge=0, description="Karbohidrat (gram)")
    fat: float = Field(ge=0, description="Lemak (gram)")


def _get_model() -> genai.GenerativeModel:
    model_name = settings.gemini_model or GEMINI_MODEL
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_INSTRUCTION,
    )


async def analyze_food_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> FoodAnalysisResult:
    """Terima bytes gambar dari Telegram, kirim ke Gemini 1.5 Flash, kembalikan analisis nutrisi."""
    if not image_bytes:
        raise ValueError("Bytes gambar kosong.")

    model = _get_model()

    response = model.generate_content(
        [
            USER_PROMPT,
            {"mime_type": mime_type, "data": image_bytes},
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )

    raw_text = response.text or ""
    if not raw_text.strip():
        raise ValueError("Gemini tidak mengembalikan respons analisis makanan.")

    data = json.loads(raw_text)
    return FoodAnalysisResult.model_validate(data)


CORRECTION_SYSTEM_INSTRUCTION = """Kamu adalah asisten analisis nutrisi makanan. Tugasmu menyesuaikan estimasi nutrisi berdasarkan koreksi teks dari user.

ATURAN WAJIB:
1. Balas HANYA dengan satu objek JSON valid. Tanpa markdown, tanpa code fence, tanpa teks sebelum atau sesudah JSON.
2. Gunakan PERSIS struktur berikut (jangan tambah atau ubah nama field):
   {"food_name": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0}
3. Kamu akan menerima data makanan sebelumnya dan instruksi koreksi user (misal: "+100g nasi", "kurang ayam", "ganti jadi 2 porsi").
4. Terapkan koreksi ke estimasi sebelumnya. Jika user menambah bahan, tambahkan nilai nutrisinya. Jika mengurangi, kurangi secara proporsional.
5. Perbarui food_name agar mencerminkan koreksi jika perlu.
6. Semua angka harus >= 0. Jangan gunakan null, string angka, atau satuan di dalam nilai numerik.
7. Estimasi harus realistis dan konsisten dengan koreksi user."""


async def recalculate_food_with_correction(
    previous: FoodAnalysisResult,
    correction_text: str,
) -> FoodAnalysisResult:
    """Hitung ulang nutrisi makanan terakhir berdasarkan teks koreksi user."""
    if not correction_text.strip():
        raise ValueError("Teks koreksi kosong.")

    model = genai.GenerativeModel(
        model_name=settings.gemini_model or GEMINI_MODEL,
        system_instruction=CORRECTION_SYSTEM_INSTRUCTION,
    )

    prompt = f"""Data makanan sebelumnya:
{previous.model_dump_json()}

Koreksi dari user: {correction_text}

Hitung ulang estimasi nutrisi setelah koreksi dan kembalikan JSON sesuai format."""

    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )

    raw_text = response.text or ""
    if not raw_text.strip():
        raise ValueError("Gemini tidak mengembalikan respons koreksi makanan.")

    data = json.loads(raw_text)
    return FoodAnalysisResult.model_validate(data)
