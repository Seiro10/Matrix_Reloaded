FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Copie de tous les fichiers du projet
COPY . /app

# Dépendances système supplémentaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libxss1 libxcomposite1 libxcursor1 \
    libxdamage1 libxi6 libxtst6 libdrm2 libgbm1 libasound2 libgtk-3-0 \
    libgtk-4-1 libgraphene-1.0-0 libwebpdemux2 libwoff1 libsecret-1-0 \
    libenchant-2-2 libmanette-0.2-0 libharfbuzz-icu0 libhyphen0 \
    gstreamer1.0-libav gstreamer1.0-plugins-good gstreamer1.0-gl \
    gstreamer1.0-plugins-base gstreamer1.0-tools ffmpeg unzip wget && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Installe playwright et ses navigateurs
RUN playwright install --with-deps
RUN npx playwright install-deps

# Installe les dépendances Python
RUN pip install --no-cache-dir --upgrade pip \
 && pip install -r requirements.txt

# Expose le port de l'API FastAPI
EXPOSE 8000

# Lancement de l'API
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
