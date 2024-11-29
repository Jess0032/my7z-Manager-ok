# For more information, please refer to https://aka.ms/vscode-docker-python
# FROM python:3.9-buster
FROM python:3.9.6-slim-buster

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# No prompting with Debian
ENV DEBIAN_FRONTEND=noninteractive

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Establish WORKDIR
WORKDIR /app

# Copy everything to WORKDIR
COPY . .

# Setup python dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Run main script
CMD ["bash", "start.sh"]
