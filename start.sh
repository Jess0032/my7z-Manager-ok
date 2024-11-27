#!/bin/bash

# If 1 and 2 don't work (god knows why), use them as Dockerfile RUN commands

# 1) Setup website
mkdir -v -p public/files;
mv -v index.html public/index.html;

# 2) Replace NGINX config with OUR config
mv -v /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak;
mv nginx.conf -v /etc/nginx/nginx.conf;

# 3) Inyect the PORT environment variable and run the NGINX service
sed -i "s/listen PORT_NUMBER_GOES_HERE/listen $PORT" /etc/nginx/nginx.conf;
/etc/init.d/nginx start;

# 4) Run the bot
python3 -m main;
