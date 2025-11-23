# ---------- Stage 1: Build React ----------
FROM node:20-alpine AS frontend

# Set working directory
WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy all frontend files
COPY frontend/ ./

# Build React app
RUN npm run build

# ---------- Stage 2: Build FastAPI backend ----------
FROM python:3.11-slim

WORKDIR /app

# Copy backend dependencies and install
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy React build from frontend stage
# NOTE: React build output is in /app/build inside stage 1
COPY --from=frontend /app/build ./frontend/build

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
