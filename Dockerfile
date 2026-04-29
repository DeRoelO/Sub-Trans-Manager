# Stage 1: Build the React SPA
FROM node:20-alpine AS build
WORKDIR /app/frontend

# Install dependencies (only package files to cache layer)
COPY frontend/package*.json ./
RUN npm ci

# Copy remainder of frontend files
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve using Python FastAPI
FROM python:3.11-slim
WORKDIR /app

# Expose PUID and PGID variables
ENV PUID=33
ENV PGID=33
ENV CONFIG_PATH=/app/config

# Install dependencies required for system + python
RUN apt-get update && apt-get install -y \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend logic
COPY backend/ ./backend/

# Copy built frontend from stage 1 into frontend/dist
COPY --from=build /app/frontend/dist ./frontend/dist/

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the API port
EXPOSE 8000

# Use the custom entrypoint
ENTRYPOINT ["/entrypoint.sh"]
