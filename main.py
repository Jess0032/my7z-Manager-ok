import asyncio
import datetime as dt
import math
import mimetypes
import os
import pathlib
import shutil
import socket
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict

import aiohttp  # Import aiohttp for HTTP requests
import humanize
import pyrogram.errors
from humanize import naturalsize
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyromod import listen

# Replace with your actual API credentials
API_ID: int = int(os.environ.get("API_ID"))
API_HASH: str = os.environ.get("API_HASH")
BOT_TOKEN: str = os.environ.get("BOT_TOKEN")
MESSAGE_CHANNEL_ID: int = int(os.environ.get("MESSAGE_CHANNEL_ID"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost")

bot = Client("my_bot", api_hash=API_HASH, api_id=API_ID, bot_token=BOT_TOKEN)

users_list = {}  # user_id: {message_id: {'mime_type': ..., 'filename': ...}}
empty_list = "📝 Still no files to compress."
users_in_channel: Dict[int, dt.datetime] = dict()


# Start HTTP server for /link command
def start_http_server():
    server_address = ("", 80)  # Listen on all interfaces, port 80
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()


# Start the HTTP server in a separate thread
http_thread = threading.Thread(target=start_http_server)
http_thread.daemon = True
http_thread.start()


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(("8.8.8.8", 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = "localhost"
    finally:
        s.close()
    return IP


def is_empty(user_id: str):
    return user_id not in users_list or not users_list[user_id]


@bot.on_message(filters=~(filters.private & filters.incoming))
async def on_chat_or_channel_message(client: Client, message: Message):
    pass


@bot.on_message()
async def on_private_message(client: Client, message: Message):
    channel = os.environ.get("CHANNEL", None)
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
        print("Channel does not exist, bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.ChatAdminRequired:
        print("Bot is not admin of the channel, bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.UserNotParticipant:
        await message.reply(
            "In order to use the bot, you must join its update channel.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join!", url=f"t.me/{channel}")]]
            ),
        )


@bot.on_message(filters.video | filters.document | filters.audio)
async def filter_files(client, message):
    user_id = message.from_user.id
    media = getattr(message, message.media.value)
    mime_type = media.mime_type
    filename = (
        media.file_name
        or f"{media.file_unique_id}{mimetypes.guess_extension(mime_type) or ''}"
    )

    if user_id in users_list:
        users_list[user_id][message.id] = {"mime_type": mime_type, "filename": filename}
    else:
        users_list[user_id] = {
            message.id: {"mime_type": mime_type, "filename": filename}
        }


@bot.on_message(filters.command("start"))
async def start_command(client, message):
    text_to_send = """
Forward all the files you want to the bot and when you are ready to compress them send /compress
Specify the maximum size in MB of the zip or not if you don't want limits. Ex: __/compress 10__
To see the list of files to compress send /list and to clear the list to compress send /clear
Use /download <URL> to download a file from the internet.
Use /rename to rename a file in your list.
"""
    await message.reply_text(text_to_send)


@bot.on_message(filters.command("list"))
async def get_list(client, message):
    user_id = message.from_user.id
    if is_empty(user_id):
        text_to_send = empty_list
    else:
        text_to_send = "📝 List of files to compress by type:\n"
        for idx, (message_id, file_info) in enumerate(
            users_list[user_id].items(), start=1
        ):
            filename = file_info["filename"]
            mime_type = file_info["mime_type"]
            new_line = f"**{idx}. {filename}** : **{mime_type}**\n"

            if len(text_to_send + new_line) > 4096:
                await message.reply_text(text_to_send)
                text_to_send = new_line
            else:
                text_to_send += new_line

    await message.reply_text(text_to_send)


@bot.on_message(filters.command("clear"))
async def clear_list(client, message):
    users_list[message.from_user.id] = {}
    await message.reply_text("📝 List cleared.")


@bot.on_message(filters.command("cache_folder"))
async def show_cache_folder(client, message):
    dirpath = pathlib.Path(f"{message.from_user.id}/")
    text = "📝 Temporary file list:\n"
    if dirpath.exists():
        for i, file in enumerate(sorted(dirpath.rglob("*.*"))):
            text += f"\n◾:{i}- **{file.name}** size: **{naturalsize(file.stat().st_size)}**"
        text += "\n\nUse **/clear_cache_folder** to remove them or **/compress** to retry compressing them."
    else:
        text += "Your temporary folder is empty."
    await message.reply_text(text)


@bot.on_message(filters.command("clear_cache_folder"))
async def clear_cache_folder(client, message):
    dirpath = pathlib.Path(f"{message.from_user.id}/")
    if dirpath.exists():
        size = sum(file.stat().st_size for file in dirpath.rglob("*.*"))
        shutil.rmtree(str(dirpath.absolute()))
        await message.reply_text(
            f"Successfully deleted files. Freed up {naturalsize(size)}."
        )
    else:
        await message.reply_text(f"Your temporary folder is empty.")


@bot.on_message(filters.command("rename"))
async def rename_file(client, message):
    user_id = message.from_user.id
    if is_empty(user_id):
        await message.reply_text("Your file list is empty.")
        return

    # Display the list of files with indices
    file_list = users_list[user_id]
    file_options = ""
    for idx, (msg_id, file_info) in enumerate(file_list.items(), start=1):
        file_options += f"{idx}. {file_info['filename']}\n"

    prompt_message = await message.reply_text(
        f"Select the file number to rename:\n{file_options}"
    )
    response = await client.listen(user_id, filters=filters.text)
    await prompt_message.delete()
    await response.delete()

    try:
        selected_idx = int(response.text.strip())
    except ValueError:
        await message.reply_text("Invalid input. Please enter a number.")
        return

    if selected_idx < 1 or selected_idx > len(file_list):
        await message.reply_text("Invalid selection.")
        return

    # Get the selected file
    selected_msg_id = list(file_list.keys())[selected_idx - 1]
    selected_file_info = file_list[selected_msg_id]
    old_filename = selected_file_info["filename"]

    # Ask for the new filename
    prompt_message = await message.reply_text(
        f"Enter the new name for **{old_filename}** (include the extension):"
    )
    response = await client.listen(user_id, filters=filters.text)
    await prompt_message.delete()
    await response.delete()
    new_filename = response.text.strip()

    # Update the filename
    users_list[user_id][selected_msg_id]["filename"] = new_filename
    await message.reply_text(f"File renamed to **{new_filename}**.")


@bot.on_message(filters.command("download"))
async def download_from_url(client, message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            "Please provide a URL to download.\nUsage: `/download <URL>`")
        return

    url = args[1].strip()

    # Validate URL
    if not url.startswith(("http://", "https://")):
        await message.reply_text("Invalid URL provided.")
        return

    # Ask for the filename
    #prompt_message = await message.reply_text(
     #   "Enter the filename to save as (include the extension):"
    #)
    #response = await client.listen(user_id, filters=filters.text)
    #await prompt_message.delete()
    #await response.delete()
    #filename = response.text.strip()

    #dirpath = pathlib.Path(f"{user_id}/files")
    #dirpath.mkdir(parents=True, exist_ok=True)
    #filepath = dirpath / filename

    progress_message = await message.reply_text("Starting download...")

    try:
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await progress_message.edit_text(
                        f"Failed to download the file. HTTP Status: {resp.status}"
                    )
                    return

                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1 MB chunks
                with open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        f.write(chunk)
                        downloaded += len(chunk)
                        await progress_bar(
                            downloaded,
                            total_size,
                            "📥 Downloading:",
                            start_time,
                            progress_message,
                            filename,
                        )
        await progress_message.delete()

        # Add to user's file list
        mime_type = resp.headers.get("Content-Type", "application/octet-stream")
        if user_id in users_list:
            users_list[user_id][message.id] = {
                "mime_type": mime_type,
                "filename": filename,
            }
        else:
            users_list[user_id] = {
                message.id: {"mime_type": mime_type, "filename": filename}
            }

        await message.reply_text(
            f"Downloaded **{filename}** and added to your file list."
        )

    except Exception as e:
        await progress_message.edit_text(f"Failed to download the file: {str(e)}")


@bot.on_message(filters.command("compress"))
async def compress(client, message):
    user_id = message.from_user.id
    if is_empty(user_id):
        await message.reply_text(empty_list)
        return
    dirpath = pathlib.Path(f"{user_id}/files")
    size = None
    args = message.text.strip().split()
    if len(args) > 1:
        size = args[1]

    file_name_message = await client.ask(
        chat_id=message.from_user.id,
        text="Send me the new filename for this task or send /cancel to stop.",
        filters=filters.text,
    )
    await file_name_message.request.delete()
    new_file_name = file_name_message.text
    if new_file_name.lower() == "/cancel":
        await message.delete()
        return

    password_message = await client.ask(
        chat_id=message.from_user.id,
        text="Send me the password 🔒 for this task or send **NO** if you don't want.",
        filters=filters.text,
    )
    await password_message.request.delete()
    password = password_message.text

    if password.lower() == "no":
        password = None

    progress_download = await message.reply_text("Downloading 📥...")
    inicial = dt.datetime.now()

    for message_id in list(users_list[user_id].keys()):
        message_obj: Message = await client.get_messages(user_id, message_id)
        filename = users_list[user_id][message_id]["filename"]
        await download_file(message_obj, dirpath, progress_download, filename)
        users_list[user_id].pop(message_id)
    await progress_download.delete()
    await message.reply_text(
        f"Downloads finished in 📥 {humanize.naturaldelta(dt.datetime.now() - inicial)}."
    )
    await message.reply_text("Compression started 🗜")
    parts_path = zip_files(dirpath, size, new_file_name, password)
    await message.reply_text("Compression finished 🗜")
    progress_upload = await message.reply_text("Uploading 📤...")
    inicial = dt.datetime.now()
    for file in sorted(parts_path.iterdir()):
        await upload_file(user_id, file, progress_upload)
    shutil.rmtree(str(parts_path.absolute()))
    await progress_upload.delete()
    await message.reply_text(
        f"Uploaded in 📤 {humanize.naturaldelta(dt.datetime.now() - inicial)}."
    )


async def download_file(
    message: Message, dirpath: pathlib.Path, progress_message: Message, filename: str
):
    filepath = dirpath / filename
    try:
        start_time = time.time()
        await message.download(
            file_name=str(filepath),
            progress=progress_bar,
            progress_args=("📥 Downloading:", start_time, progress_message, filename),
        )
    except Exception as e:
        print(e)


async def upload_file(user_id: str, file: pathlib.Path, progress_message: Message):
    try:
        start_time = time.time()
        await bot.send_document(
            user_id,
            str(file),
            progress=progress_bar,
            progress_args=("📤 Uploading:", start_time, progress_message, file.name),
        )
    except Exception as exc:
        print(exc)


async def progress_bar(current, total, status_msg, start, msg, filename):
    present = time.time()
    if round((present - start) % 20) == 0 or current == total:
        speed = current / (present - start) if present - start > 0 else 0
        percentage = current * 100 / total if total > 0 else 0
        time_to_complete = round(((total - current) / speed)) if speed > 0 else 0
        time_to_complete = humanize.naturaldelta(time_to_complete)
        progressbar = "[{0}{1}]".format(
            "".join(["🟢" for _ in range(math.floor(percentage / 10))]),
            "".join(["⚫" for _ in range(10 - math.floor(percentage / 10))]),
        )

        current_message = f"""**{status_msg} {filename}** {round(percentage, 2)}%
{progressbar}

**⚡ Speed**: {humanize.naturalsize(speed)}/s
**📚 Done**: {humanize.naturalsize(current)}
**💾 Size**: {humanize.naturalsize(total)}
**⏰ Time Left**: {time_to_complete}"""
        try:
            await msg.edit_text(current_message)
        except pyrogram.errors.MessageNotModified:
            pass


def zip_files(dirpath: pathlib.Path, size: str, new_file_name: str, password: str):
    import zipfile
    from zipfile import ZipFile

    # Calculate the size in bytes if size is provided
    max_size = int(size) * 1024 * 1024 if size else None

    zip_dir = pathlib.Path(f"{dirpath.parent}/compressed")
    zip_dir.mkdir(parents=True, exist_ok=True)

    # Create a zip file
    zip_path = zip_dir / f"{new_file_name}.zip"

    with ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        if password:
            zipf.setpassword(password.encode())
        for file in dirpath.iterdir():
            zipf.write(file, arcname=file.name)

    # Handle splitting the zip file if max_size is specified
    if max_size and zip_path.stat().st_size > max_size:
        parts = split_file(zip_path, max_size)
        return parts
    else:
        return zip_dir


def split_file(file_path: pathlib.Path, max_size: int):
    parts_dir = file_path.parent / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    part_num = 1
    with open(file_path, "rb") as f:
        chunk = f.read(max_size)
        while chunk:
            part_path = parts_dir / f"{file_path.stem}.part{part_num}{file_path.suffix}"
            with open(part_path, "wb") as part_file:
                part_file.write(chunk)
            part_num += 1
            chunk = f.read(max_size)
    return parts_dir


async def start():
    print("Bot is running...")
    await bot.send_message(MESSAGE_CHANNEL_ID, "Bot has started.")


@bot.on_message(filters.command("link"))
async def generate_link(client, message):
    if not message.reply_to_message:
        await message.reply_text("Please reply to a file to generate a link.")
        return

    replied_message = message.reply_to_message

    # Check if the message contains downloadable media
    media_types = ["document", "video", "audio", "photo"]
    media = None
    for media_type in media_types:
        media = getattr(replied_message, media_type, None)
        if media is not None:
            break

    if media is None:
        await message.reply_text(
            "The replied message doesn't contain any downloadable media."
        )
        return

    user_id = message.from_user.id
    dirpath = pathlib.Path(f"{user_id}/files")
    dirpath.mkdir(parents=True, exist_ok=True)

    # Determine the filename
    if isinstance(media, pyrogram.types.Photo):
        filename = f"{media.file_unique_id}.jpg"
    else:
        filename = (
            media.file_name
            or f"{media.file_unique_id}{mimetypes.guess_extension(media.mime_type) or ''}"
        )

    filepath = dirpath / filename

    # Check if the file already exists
    if not filepath.exists():
        progress_message = await message.reply_text("Downloading the file...")
        try:
            await replied_message.download(
                file_name=str(filepath),
                progress=progress_bar,
                progress_args=(
                    "📥 Downloading:",
                    time.time(),
                    progress_message,
                    filename,
                ),
            )
            await progress_message.delete()
        except Exception as e:
            await progress_message.edit_text(f"Failed to download the file: {str(e)}")
            return

    # Generate the link
    relative_filepath = filepath.relative_to(pathlib.Path.cwd())
    file_url = f"{PUBLIC_URL}/{relative_filepath.as_posix()}"
    await message.reply_text(f"Here is your link:\n{file_url}")


if __name__ == "__main__":
    bot.start()
    asyncio.get_event_loop().run_until_complete(start())
    idle()
