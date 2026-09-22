# Imagen de la API. El frontend React se despliega aparte (Vercel/Netlify) o se
# sirve desde otro contenedor; aqui va el backend + tools (y Streamlit, que se
# puede arrancar con `docker run ... streamlit run app.py --server.port 8501`).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY tools/ ./tools/

# La memoria se guarda en /data: monta un volumen para que persista.
RUN mkdir -p /data && useradd --create-home appuser && chown -R appuser /data /app
USER appuser

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health',timeout=3)"

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
