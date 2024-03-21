FROM python:3.12-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY ./pubsub.py .
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "pubsub.py"]
