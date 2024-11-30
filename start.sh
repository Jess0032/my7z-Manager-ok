#!/bin/bash

echo "WEB SERVER PORT = $PORT"

THE_URL="https://github.com/carlos-a-g-h/asere-hfs/releases/download/2023-08-23/asere-hfs.amd64"
#wget "$THE_URL" -O asere-hfs
#curl -o asere-hfs "$THE_URL"
python3 pull.py asere-hfs "$THE_URL"
chmod +x asere-hfs
./asere-hfs --port $PORT --master "/app/public" &

echo "WEB SERVER PID = $(pidof asere-hfs)"

# debug
echo "files {"
find .
echo "} files"

# 4) Run the bot
python3 -m main;
