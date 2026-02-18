# ---------- frontend build stage ----------
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# ---------- runtime stage ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

RUN apt-get update \
    && apt-get install -y nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY --from=frontend-build /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY start.sh /usr/local/bin/start-app.sh
RUN chmod +x /usr/local/bin/start-app.sh

EXPOSE 10000

CMD ["/usr/local/bin/start-app.sh"]
