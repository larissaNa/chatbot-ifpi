FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

# COPY apps/credenciais.json 
# ENV GOOGLE_APPLICATION_CREDENTIALS="/apps/credenciais.json"
# ENV GOOGLE_CLOUD_PROJECT="gen-lang-client-0261212364"

RUN pip install --upgrade pip

# Dependências para Playwright e Chromium
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

# Instala Chromium do Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

CMD ["gunicorn", "--config", "gunicorn-cfg.py", "run:app"]
