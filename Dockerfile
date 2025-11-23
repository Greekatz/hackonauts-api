# ---------------------------
# Step 1: Build React frontend
# ---------------------------
FROM node:20-alpine AS frontend

WORKDIR /app/frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install --silent

# Copy all frontend source code
COPY frontend/ ./

# Build React app
RUN npm run build

# Verify build folder exists
RUN ls -la /app/frontend/build

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
COPY --from=frontend /app/frontend/build ./frontend/build

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
