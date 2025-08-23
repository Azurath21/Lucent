# Multi-language image: Node.js + Python + Chromium for Selenium
# Use an official Node image (Debian-based) so we can apt-get Python and Chromium
FROM node:20-bullseye

# Install Python 3, pip, Chromium, and fonts/libs needed by Chromium
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    chromium \
    xvfb \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libnss3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxshmfence1 \
    libxrandr2 \
    libu2f-udev \
    libvulkan1 \
    xdg-utils \
  && rm -rf /var/lib/apt/lists/*

# Set Chrome binary path for our scraper
ENV CHROME_BIN=/usr/bin/chromium
ENV DISPLAY=:99
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /app

# Install Node deps first (better layer cache)
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev

# Install Python deps
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose port (Render will set $PORT)
EXPOSE 5000
ENV PORT=5000

# Start a virtual X display, then launch the Node server
CMD ["bash", "-lc", "Xvfb :99 -screen 0 1280x1024x24 & node server.js"]
