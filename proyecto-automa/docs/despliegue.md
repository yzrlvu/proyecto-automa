# Guía de Despliegue y Operación

## 1. Requisitos
- Docker + Docker Compose (o Python 3.12 + PostgreSQL 16 local)
- Claves: `ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`, `TELEGRAM_BOT_TOKEN`

## 2. Despliegue local con Docker (recomendado)
```bash
cp .env.example .env        # completar claves
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml exec api python -m scripts.seed
docker compose -f deploy/docker-compose.yml exec api python -m scripts.index_kb
curl http://localhost:8000/api/v1/health
```

## 3. Despliegue manual (desarrollo)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed
python -m scripts.index_kb
uvicorn app.main:app --reload
```

## 4. Configurar webhook de Telegram
```bash
# exponer con un túnel (ej. cloudflared o ngrok) y registrar:
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://TU_DOMINIO/api/v1/webhook/telegram"
```

## 5. Operación
- **Salud**: `GET /api/v1/health`
- **KPIs / ROI**: `GET /api/v1/metricas`
- **Trazas**: proyecto `citas-clinica-grupo10` en https://smith.langchain.com
- **Evals**: `python -m evals.eval_langsmith`
- **Scheduler**: jobs `recordatorios` y `liberar_cupos` cada 5 min (logs de uvicorn)
- **Auditoría**: tabla `eventos` en PostgreSQL (todos los eventos de dominio)

## 6. Producción (nube)
El contenedor es stateless (estado en PostgreSQL/Chroma), por lo que puede
desplegarse en Railway, Render, Fly.io o AWS ECS Fargate + RDS sin cambios:
solo definir las variables de entorno y montar volumen para `chroma_db/`.
