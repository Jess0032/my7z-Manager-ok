# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9-buster

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Establish WORKDIR
WORKDIR /app

# Copy everything to WORKDIR
COPY . .

# Setup python dependencies and NGINX
RUN apt install -yy nginx; python -m pip install --no-cache-dir -r requirements.txt

# Run main script
CMD ["bash", "start.sh"]
