FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home sivrce
COPY --chown=sivrce:sivrce . .
RUN mkdir -p /app/private_uploads && chown sivrce:sivrce /app/private_uploads
USER sivrce
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
