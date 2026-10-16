FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/paper_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home reader && mkdir /data && chown reader:reader /data
COPY services /app/services
USER reader
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "services.paper_api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
