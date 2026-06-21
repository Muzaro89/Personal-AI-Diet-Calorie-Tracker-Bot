# Personal-AI-Diet-Calorie-Tracker-Bot
A personalized, AI-powered nutrition and calorie tracking assistant built using **FastAPI**, **Gemini 1.5 Flash**, and **Telegram Bot API**. This is a **personal project** designed to logs daily food intake with zero friction—simply by snapping a photo of the meal and sending it via Telegram.

(This is a personal ongoing project)

# 🍳 NutriBot: AI-Powered Dietary Tracker & Food Journal

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini AI](https://img.shields.io/badge/Gemini%20AI-1.5%20Flash-orange.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NutriBot** adalah asisten personal berbasis chatbot (Telegram) yang dirancang untuk melacak konsumsi kalori dan nutrisi harian dengan friksi seminimal mungkin. Cukup ambil foto makananmu, kirimkan ke bot, dan AI akan menganalisis perkiraan kalori, makronutrisi, serta memberikan rekapitulasi harian secara otomatis.

> 💡 **Kenapa NutriBot?** Aplikasi pencatat kalori konvensional mengharuskan kamu mencari nama makanan dan menimbang beratnya secara manual setiap saat. NutriBot memotong proses itu: **Foto, Kirim, Selesai.**

---

## ✨ Fitur Utama

- **📷 Instant Food Recognition:** Kirim foto makanan apa saja, dan teknologi Multimodal LLM (Gemini 1.5 Flash) akan mengidentifikasi jenis makanan beserta porsinya.
- **📊 Macro Breakdown (JSON Structured Output):** AI secara otomatis mengembalikan estimasi kalori (kkal), protein (g), karbohidrat (g), dan lemak (g) dalam format terstruktur.
- **🔄 Interactive Text Correction:** Akurasi foto meleset? Cukup balas pesan bot dengan teks (misal: `"+100g nasi"` atau `"kurangi porsi ayam"`), dan sistem akan menghitung ulang secara dinamis.
- **📈 Daily & Weekly Tracking:** Menyimpan log harian ke database lokal dan memberikan kalkulasi total kalori yang sudah dikonsumsi hari ini.
- **🗞️ Weekly Automated Report (Coming Soon):** Rangkuman dan analisis kualitas diet mingguan yang dikirim langsung setiap akhir pekan menggunakan AI insight.

---

## 🏗️ Struktur Arsitektur

Sistem ini dibangun dengan pendekatan *event-driven* menggunakan webhook:
```bash
[User] ---> (Kirim Foto / Koreksi Teks) ---> [Telegram Bot API]
|
(Webhook HTTP POST)
v
[FastAPI Backend]
|
+-------------------------+-------------------------+
| (Kirim Foto + Prompt)                             | (Simpan/Update Data)
v                                                   v
[Gemini API / LLM]                                    [SQLite DB]
|                                                   |
(JSON: Kalori & Makro)                                        |
+-------------------------<-------------------------+
|
(Format Pesan Teks)
v
[User] <--- (Balasan Analisis & Total Hari Ini) <-- [Bot API]

---
```
## 🛠️ Tech Stack & Dependensi

- **Backend Framework:** FastAPI (Python)
- **AI Engine:** Google GenAI SDK (Gemini 1.5 Flash)
- **Database / ORM:** SQLite & SQLAlchemy
- **Tunneling (Lokal):** Ngrok / Localtunnel
- **Task Scheduler:** APScheduler

---

## 🚀 Memulai (Local Setup)

Ikuti langkah-langkah berikut untuk menjalankan proyek ini di mesin lokal kamu menggunakan **Cursor IDE** atau terminal standar.

### 1. Prasyarat
Pastikan kamu telah memiliki:
- Python 3.10 ke atas terinstal.
- Token Bot Telegram (bisa didapatkan gratis melalui [@BotFather](https://t.me/BotFather)).
- Google AI Studio API Key (bisa didapatkan di [Google AI Studio](https://aistudio.google.com/)).

### 2. Kloning Repositori & Instalasi
```bash
# Kloning repositori ini
git clone [https://github.com/username/food-tracker-bot.git](https://github.com/username/food-tracker-bot.git)
cd food-tracker-bot

# Instal dependensi yang diperlukan
pip install -r requirements.txt
```

3. Konfigurasi Environment
Buat sebuah berkas .env di direktori utama (kamu bisa menyalin dari .env.example) dan lengkapi kredensial berikut:
```bash
TELEGRAM_BOT_TOKEN=isi_token_telegram_kamu
GEMINI_API_KEY=isi_api_key_gemini_kamu
DATABASE_URL=sqlite:///./food_tracker.db
```

4. Menjalankan Server
Jalankan server FastAPI menggunakan Uvicorn:
```bash
uvicorn main:app --reload
```
Server lokal kamu akan berjalan di http://127.0.0.1:8000.


5. Ekspos ke Publik & Set Webhook
Karena Telegram membutuhkan URL HTTPS publik untuk mengirim data webhook, gunakan Ngrok:
```bash
ngrok http 8000
```
Salin URL HTTPS yang diberikan oleh Ngrok (misal: https://abcd-123.ngrok-free.app), lalu daftarkan URL tersebut sebagai webhook resmi bot kamu melalui browser atau curl:
```bash
[https://api.telegram.org/bot](https://api.telegram.org/bot)<TELEGRAM_BOT_TOKEN>/setWebhook?url=[https://abcd-123.ngrok-free.app/webhook](https://abcd-123.ngrok-free.app/webhook)
```
Buka aplikasi Telegram, cari bot kamu, dan silakan uji coba dengan mengirimkan foto makanan pertamamu! 🚀

⚠️ Disclaimer & Limitasi
Proyek ini dibuat untuk keperluan personal tracking dan jurnal praktis. Estimasi kalori yang dihasilkan oleh Computer Vision/LLM didasarkan pada visual 2D dan komponen umum masakan, sehingga tingkat akurasinya tidak bersifat absolut. Selalu gunakan fitur koreksi teks untuk hasil yang mendekati realitas porsi makanan Anda.

📄 Lisensi
Proyek ini dilisensikan di bawah MIT License - lihat berkas LICENSE untuk detail lebih lanjut.

update 21/06
hasil sudah menunjukkan bahwa botnya sudah berjalan, tapi ada kendala di model llm yang digunakan sehingga saat mengirimkan foto makanan, respon yang didapatkan adalah error limit penggunaan. dibutuhkan pergantian model yang digunakan. proyek ini akan hiatus seminggu karena tgl 25 akan sidang tesis


