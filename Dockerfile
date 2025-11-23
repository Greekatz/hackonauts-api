# ---------- Stage 1: Build React ----------
FROM node:20-alpine AS frontend

WORKDIR /app

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy source code and build
COPY frontend/ ./
RUN npm run build

# Verify build exists (Vite creates 'dist')
RUN ls -la /app/dist

# ---------- Stage 2: Serve with Nginx ----------
FROM nginx:alpine

# Copy the build output to replace the default nginx contents.
# Source: /app/dist (from Stage 1)
# Dest: /usr/share/nginx/html (standard Nginx static file location)
COPY --from=frontend /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]