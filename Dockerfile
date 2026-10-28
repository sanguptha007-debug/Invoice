FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY app.py .
EXPOSE 80
CMD ["python", "app.py"]
