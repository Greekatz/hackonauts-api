# ---------------------------
# Step 1: Build React frontend
# ---------------------------
FROM node:20-alpine AS frontend

WORKDIR /app

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install --silent

# Copy frontend source code and build
COPY frontend/ ./
RUN npm run build

# ---------------------------
# Step 2: Build FastAPI backend
# ---------------------------
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./ 

# Copy React build from previous stage
COPY --from=frontend /app/build ./frontend/build

# Expose port
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
