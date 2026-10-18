FROM node:22-alpine AS frontend
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /workspace
COPY backend /workspace/backend
COPY --from=frontend /workspace/frontend/dist /workspace/frontend/dist
COPY .env.example /workspace/.env.example
RUN pip install --no-cache-dir -e /workspace/backend
ENV PYTHONPATH=/workspace/backend
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
