FROM python:3.11-slim

# Install system deps
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Copy and install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot
COPY . .

# Run
CMD ["python", "bot.py"]
