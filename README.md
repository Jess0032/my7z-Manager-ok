# CompressBot

A simple telegram bot that takes a list of files sent by the user and returns them 7zipped or merged.


## Commands

```
start - Fast help of Bot 😎
list - list of files to merge / compress
compress - compress files (optional specify part size in MB)
download - download direct links and add to List
link - get direct link by reply to a file on tg or send link without reply a file to get url to your files 
rename - rename files from list by number id
clear - Clear the file list
cache_folder - show folder cache
clear_cache_folder - clear folder cache
full_clear - admin only

```

## Env Vars

```
BOT_TOKEN - Make a bot from https://t.me/BotFather and enter the token here.
API_ID - Get this value from https://my.telegram.org/apps
API_HASH - Get this value from https://my.telegram.org/apps
ADMIN_ID - Id of owner 
MESSAGE_CHANNEL_ID - id of telegram channel add bot admin in this channel
CHANNEL - link of public channel without https://t.me/
PUBLIC_URL - Url or ip where is hosted the Bot.

```

## Deploy
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yadianluffy/MergeBotPyrogram)

