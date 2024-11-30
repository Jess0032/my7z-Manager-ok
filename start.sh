#!/bin/bash

# HTTP File Server (HFS) URL
URL_HFS="https://github.com/carlos-a-g-h/asere-hfs/releases/download/2023-08-23/asere-hfs.amd64"

# Path to public dir
PATH_PUBLIC="/app/public"

# (debug) Show the PORT env var
echo "WEB SERVER PORT = $PORT"

# Download the HFS binary using the pull.py script
python3 pull.py asere-hfs "$URL_HFS"

# Create public dir
mkdir -p "$PATH_PUBLIC"

# Give execution permit and run the HFS in background
chmod +x asere-hfs
./asere-hfs --port $PORT --master "$PATH_PUBLIC" &

# (debug) Show the PID of the HFS
echo "HTTP FILE SERVER PID = $(pidof asere-hfs)"

# (debug) Files
echo "files {"
find .
echo "} files"

# Run the bot
python3 -m main;
