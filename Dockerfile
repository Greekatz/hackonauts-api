# ---------------------------
# Step 1: Build React frontend
# ---------------------------
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install --silent
COPY frontend/ ./
RUN npm run build
# Optional: verify build exists
RUN ls -la /app/build

# ---------------------------
# Step 2: Build FastAPI backend
# ---------------------------
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/build ./frontend/build
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
