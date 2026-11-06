FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime-base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/requirements*.txt ./backend/
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime-base AS runtime-full
RUN pip install --no-cache-dir torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r backend/requirements-iqa.txt

FROM runtime-base AS classical
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY configs/ ./configs/
COPY --from=frontend /frontend/dist ./frontend/dist
RUN mkdir -p outputs checkpoints
FROM runtime-full AS full
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY configs/ ./configs/
COPY --from=frontend /frontend/dist ./frontend/dist
RUN mkdir -p outputs checkpoints
ENV LUMA_ENABLE_IQA=true
