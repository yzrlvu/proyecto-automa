# Dockerfile para Hugging Face Spaces (Docker SDK, puerto 7860)
FROM python:3.12-slim

# Usuario no-root (requerido por HF Spaces, uid 1000)
RUN useradd -m -u 1000 user
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    HOME=/home/user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-descarga el modelo de embeddings para que el arranque sea rápido
RUN python -c "from langchain_huggingface import HuggingFaceEmbeddings; \
    HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')"

# En runtime no consultar el Hub: el modelo ya está en la imagen
# (evita cuelgues por rate limiting de peticiones anónimas desde Spaces)
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

RUN chown -R user:user /app
USER user

EXPOSE 7860
# Construye el índice RAG (si falta) y arranca la API con el frontend
CMD ["sh", "-c", "python -m scripts.index_kb && uvicorn app.main:app --host 0.0.0.0 --port 7860"]
