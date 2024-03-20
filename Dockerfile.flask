FROM python:3.12-slim
EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .
RUN python -m pip install -r requirements.txt

CMD ["python", "app.py"]
