# Official Python image (includes SQLite). A fixed minor version keeps builds reproducible;
# ubuntu:latest no longer allows a system-wide 'pip install'.
FROM python:3.12-slim

WORKDIR /app

# Install the Python packages first, so this layer is reused when only the code changes
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Code, texts and (optionally) seeds/ with a downloaded fdb.db to restart from
COPY . /app

# Data folder: mount the persistent CaaS volume here (it may start empty).
# The image itself contains no runtime data (see .dockerignore).
ENV BFORE_CONTAINER=1 DATA_DIR=/app/data PYTHONUNBUFFERED=1
RUN mkdir -p /app/data

# The server expects the app on port 5000 (locally the default is 8500)
ENV PORT=5000
EXPOSE 5000

CMD ["python3", "app.py"]
