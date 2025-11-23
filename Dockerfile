# ---------- Stage 1: Build React ----------
FROM node:20-alpine AS frontend

WORKDIR /app

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy source code and build
COPY frontend/ ./
RUN npm run build

# Verify build exists (Vite creates 'dist', not 'build')
RUN ls -la /app/dist

# ---------------------------
# Step 2: Build FastAPI backend
# ---------------------------
FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy React build from frontend stage
# Source: /app/dist (where Vite put it in Stage 1)
# Dest: ./frontend/build (where your FastAPI likely expects it)
COPY --from=frontend /app/dist ./frontend/build

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]