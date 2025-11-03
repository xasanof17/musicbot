# ─── Base Python Image ─────────────────────────────
FROM python:3.11-slim

# ─── Prevent Python buffering ─────────────────────
ENV PYTHONUNBUFFERED=1

# ─── System Dependencies ──────────────────────────
# Includes ffmpeg for audio conversion and Chromaprint for AcoustID fingerprinting
RUN apt-get update && \
    apt-get install -y ffmpeg libchromaprint-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ─── Set Work Directory ───────────────────────────
WORKDIR /app

# ─── Install Dependencies ─────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Copy Project Files ───────────────────────────
COPY . .

# ─── Start the Bot ────────────────────────────────
CMD ["python", "bot.py"]
