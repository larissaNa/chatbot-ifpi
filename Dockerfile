FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

# COPY apps/credenciais.json 
# ENV GOOGLE_APPLICATION_CREDENTIALS="/apps/credenciais.json"
# ENV GOOGLE_CLOUD_PROJECT="gen-lang-client-0261212364"

RUN pip install --upgrade pip

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
    fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "--config", "gunicorn-cfg.py", "run:app"]
