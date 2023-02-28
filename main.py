import math
import asyncio
import mimetypes
import pathlib
import datetime as dt
import humanize
from typing import Dict
import pyrogram.errors
from humanize import naturalsize
from pyromod import listen
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


from functions import *

API_ID: int = int(os.environ.get("API_ID"))
API_HASH: str = os.environ.get("API_HASH")
BOT_TOKEN: str = os.environ.get("BOT_TOKEN")
MESSAGE_CHANNEL_ID: int = int(os.environ.get("MESSAGE_CHANNEL_ID"))


bot = Client("my_bot", api_hash=API_HASH, api_id=API_ID, bot_token=BOT_TOKEN)


users_list = {}
empty_list = "📝 Still no files to compress."
formats = ['text/plain', 'application/pdf']
users_in_channel: Dict[int, dt.datetime] = dict()
    
@bot.on_message(filters=~(filters.private & filters.incoming))
async def on_chat_or_channel_message(client: Client, message: Message):
    pass


@bot.on_message()
async def on_private_message(client: Client, message: Message):
    channel = os.environ.get("CHANNEL")
    if not channel:
        return message.continue_propagation()
    if in_channel_cached := users_in_channel.get(message.from_user.id):
        if dt.datetime.now() - in_channel_cached < dt.timedelta(days=1):
            return message.continue_propagation()
    try:
        if await client.get_chat_member(channel, message.from_user.id):
            users_in_channel[message.from_user.id] = dt.datetime.now()
            return message.continue_propagation()
    except pyrogram.errors.UsernameNotOccupied:
        print("Channel does not exist, therefore bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.ChatAdminRequired:
        print("Bot is not admin of the channel, therefore bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.UserNotParticipant:
        await message.reply("In order to use the bot you must join it's update channel.",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton('Join!', url=f't.me/{channel}')]]
                            ))    


@bot.on_message(filters.video | filters.document | filters.audio)
async def filter_files(client, message):
    user_id = message.from_user.id

    mime_type = getattr(message, message.media.value).mime_type

    if user_id in users_list:
        users_list[user_id][message.id] = mime_type

    else:
        users_list[user_id] = {message.id: mime_type}


def is_empty(user_id: str):
    return user_id not in users_list or not users_list[user_id]


@bot.on_message(filters.command("start"))
async def get_list(client, message):
    text_to_send = """
Forward all the files you want to the bot and when you are ready to compress them send /compress
Specify the maximum size in MB of the zip or not if you don't want limits. Ex: __/compress 10__
To see the list of files to compress send /list and to clear the list to compress send /clear
"""
    await message.reply_text(text_to_send)


@bot.on_message(filters.command("list"))
async def get_list(client, message):
    user_id = message.from_user.id
    if is_empty(user_id):
        text_to_send = empty_list
    else:
        text_to_send = "📝 List of files to compress by type:\n"
        for message_id in users_list[user_id]:
            message = await client.get_messages(user_id, message_id)
            filename = getattr(message, message.media.value).file_name
            mime_type = getattr(message, message.media.value).mime_type
            new_line = f'**{filename}** : **{mime_type}**\n'

            if len(text_to_send+new_line)>4096:
                await message.reply_text(text_to_send)
                text_to_send=new_line
            else:
                text_to_send+=new_line

    await message.reply_text(text_to_send)


@bot.on_message(filters.command("clear"))
async def clear_list(client, message):
    users_list[message.from_user.id] = {}
    await message.reply_text('📝 list cleaned')


@bot.on_message(filters.command("cache_folder"))
async def clear_list(client, message):
    dirpath = Path(f'{message.from_user.id}/')
    text = '📝 Temporary file list:\n'
    for i, file in enumerate(sorted(dirpath.rglob('*.*'))):
        text += f'\n◾:{i}- **{file.name}** size: **{naturalsize(file.stat().st_size)}**'
    text += '\n\nUse **/clear_cache_folder** to remove them or **/compress** to retry compressing them.'
    await message.reply_text(text)


@bot.on_message(filters.command("clear_cache_folder"))
async def clear_list(client, message):
    dirpath = Path(f'{message.from_user.id}/')
    if (dirpath.exists()):
        size = sum(file.stat().st_size for file in dirpath.rglob('*.*'))
        shutil.rmtree(str(dirpath.absolute()))
        await message.reply_text(f'Successfully deleted files. {naturalsize(size)}')
    else:
        await message.reply_text(f'Your temporary folder is empty.')


@bot.on_message(filters.regex('\/compress\s*(\d*)'))
async def compress(client, message):
    user_id = message.from_user.id
    if is_empty(user_id):
        await message.reply_text(empty_list)
        return
    dirpath = Path(f'{user_id}/files')
    size = message.matches[0].group(1)
    file_name = await client.ask(chat_id=message.from_user.id,
                                 text="Send me the New FileName for this task or send /cancel to stop",
                                 filters=filters.text)
    await file_name.request.delete()
    new_file_name = file_name.text
    if new_file_name.lower() == "/cancel":
        await message.delete()
        return

    password = await client.ask(chat_id=message.from_user.id,
                                text="Send me the password 🔒 for this task or send **NO** if you don't want.",
                                filters=filters.text)
    await password.request.delete()

    password = password.text

    if str.lower(password) == 'no':
        password = None

    progress_download = await message.reply_text("Downloading 📥...")
    inicial = dt.datetime.now()
    for message_id in [x for x in users_list[user_id]]:
        message: Message = await client.get_messages(user_id, message_id)
        await download_file(message, dirpath, progress_download)
        users_list[user_id].pop(message_id)
    await progress_download.delete()
    await message.reply_text(
        f"Downloads finished in 📥 {humanize.naturaldelta(dt.datetime.now() - inicial)}.")
    await message.reply_text("Compression started 🗜")
    parts_path = zip_files(dirpath, size, new_file_name, password)
    await message.reply_text("Compression finished 🗜")
    progress_upload = await message.reply_text("Uploading 📤...")
    inicial = dt.datetime.now()
    for file in sorted(parts_path.iterdir()):
        await upload_file(user_id, file, progress_upload)
    shutil.rmtree(str(parts_path.absolute()))
    await progress_upload.delete()
    await message.reply_text(f"Uploaded in 📤 {humanize.naturaldelta(dt.datetime.now() - inicial)}.")


async def download_file(message: Message, dirpath: str, progress_message: Message):
    if message.video:
        if message.caption:
            caption = message.caption.split("\n")[0]
            filename = f'{caption}{pathlib.Path(message.video.file_name).suffix if message.video.file_name else mimetypes.guess_extension(message.video.mime_type)}'
        else:
            filename = message.video.file_name if message.video.file_name else f'{message.video.file_unique_id}{mimetypes.guess_extension(message.video.mime_type)}'
    else:
        filename = getattr(message, message.media.value).file_name

    print(filename)
    filepath = f'{dirpath}/{filename}'
    try:
        start_time = time.time()
        await message.download(file_name=filepath, progress=progress_bar,
                               progress_args=("📥 Downloading:", start_time, progress_message, filename))
    except Exception as e:
        print(e)


async def upload_file(user_id: str, file: str, progress_message: Message):
    try:
        start_time = time.time()
        await bot.send_document(user_id, file, progress=progress_bar,
                                progress_args=("📤 Uploading:", start_time, progress_message, pathlib.Path(file).name))

    except Exception as exc:
        print(exc)


async def progress_bar(current, total, status_msg, start, msg, filename):
    present = time.time()
    if round((present - start) % 3) == 0 or current == total:
        speed = current / (present - start)
        percentage = current * 100 / total
        time_to_complete = round(((total - current) / speed))
        time_to_complete = humanize.naturaldelta(time_to_complete)
        progressbar = "[{0}{1}]".format(
            ''.join(["🟢" for i in range(math.floor(percentage / 10))]),
            ''.join(["⚫" for i in range(10 - math.floor(percentage / 10))])
        )
        current_message = f"""**{status_msg} {filename}** {round(percentage, 2)}%
{progressbar}

**⚡ Speed**: {humanize.naturalsize(speed)}/s
**📚 Done**: {humanize.naturalsize(current)}
**💾 Size**: {humanize.naturalsize(total)}
**⏰ Time Left**: {time_to_complete}"""
        try:
            await msg.edit_text(current_message)
        except pyrogram.errors.MessageNotModified as e:
            print(e)
            pass

async def start():
    print('Running')
    await bot.send_message(MESSAGE_CHANNEL_ID, "Hello.")

if __name__ == "__main__":
    bot.start()
    asyncio.get_event_loop().create_task(start())
    idle()
