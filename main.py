import os
import math
import time
import shutil
import asyncio
import mimetypes
import pathlib
import datetime as dt
import humanize
from typing import Dict
import pyrogram.errors
from pyromod import listen
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import threading
import aiohttp  # for HTTP requests

# Constants for environment variables
API_ID: int = int(os.environ.get("API_ID"))
API_HASH: str = os.environ.get("API_HASH")
BOT_TOKEN: str = os.environ.get("BOT_TOKEN")
MESSAGE_CHANNEL_ID: int = int(os.environ.get("MESSAGE_CHANNEL_ID"))

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global variables
users_list: Dict[int, Dict] = {}
empty_list_msg = "📝 Still no files to compress."
users_in_channel: Dict[int, dt.datetime] = {}

# Utility function to check if user list is empty
def is_empty(user_id: int) -> bool:
    return user_id not in users_list or not users_list[user_id]

# Start an HTTP server in the background for handling download links
def start_http_server():
    server_address = ("", 8000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

# Start HTTP server in a separate thread
threading.Thread(target=start_http_server, daemon=True).start()

# Get the local IP address for link generation
def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = "localhost"
    finally:
        s.close()
    return IP

# Command: /start
@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    text = (
        "Forward files to the bot and use /compress to compress them.\n"
        "You can specify a size limit (in MB) for compression.\n"
        "Commands:\n"
        "/compress <size> - Compress files.\n"
        "/list - Show the list of files.\n"
        "/clear - Clear the file list.\n"
        "/download <URL> - Download a file from a URL.\n"
        "/rename - Rename a file.\n"
        "/link - Generate a download link for a file."
    )
    await message.reply_text(text)

# Command: /list - List files
@bot.on_message(filters.command("list"))
async def get_list(client: Client, message: Message):
    user_id = message.from_user.id
    if is_empty(user_id):
        await message.reply_text(empty_list_msg)
        return

    file_list_msg = "📝 List of files to compress:\n"
    for idx, (msg_id, file_info) in enumerate(users_list[user_id].items(), start=1):
        file_name, mime_type = file_info['filename'], file_info['mime_type']
        new_line = f"{idx}. {file_name} ({mime_type})\n"
        if len(file_list_msg + new_line) > 4096:  # Telegram message size limit
            await message.reply_text(file_list_msg)
            file_list_msg = new_line
        else:
            file_list_msg += new_line

    await message.reply_text(file_list_msg)

# Command: /clear - Clear file list
@bot.on_message(filters.command("clear"))
async def clear_list(client: Client, message: Message):
    user_id = message.from_user.id
    users_list[user_id] = {}
    await message.reply_text("📝 List cleared.")

# Command: /download - Download a file from a URL
@bot.on_message(filters.command("download"))
async def download_from_url(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.reply_text("Please provide a valid URL.\nUsage: `/download <URL>`")
        return

    url = args[1]
    if not url.startswith(("http://", "https://")):
        await message.reply_text("Invalid URL. Must start with http:// or https://")
        return

    # Ask for the filename to save as
    prompt_msg = await message.reply_text("Enter the filename to save the file as (including extension):")
    filename_response = await client.listen(user_id, filters=filters.text)
    filename = filename_response.text.strip()

    dirpath = pathlib.Path(f"{user_id}/files")
    dirpath.mkdir(parents=True, exist_ok=True)
    filepath = dirpath / filename

    progress_msg = await message.reply_text("Downloading file...")

    try:
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await progress_msg.edit_text(f"Failed to download the file. HTTP Status: {response.status}")
                    return

                total_size = int(response.headers.get("Content-Length", 0))
                with open(filepath, "wb") as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(1024 * 1024):  # 1 MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        await update_progress_bar(
                            downloaded, total_size, "📥 Downloading", start_time, progress_msg, filename
                        )
        await progress_msg.delete()

        # Add downloaded file to user's list
        mime_type = response.headers.get("Content-Type", "application/octet-stream")
        if user_id in users_list:
            users_list[user_id][message.id] = {"mime_type": mime_type, "filename": filename}
        else:
            users_list[user_id] = {message.id: {"mime_type": mime_type, "filename": filename}}

        await message.reply_text(f"Downloaded and saved as **{filename}**.")
    except Exception as e:
        await progress_msg.edit_text(f"Error downloading the file: {str(e)}")

# Progress bar updater
async def update_progress_bar(current, total, status_msg, start, msg, filename):
    elapsed_time = time.time() - start
    percentage = current * 100 / total if total > 0 else 0
    speed = current / elapsed_time if elapsed_time > 0 else 0
    remaining_time = (total - current) / speed if speed > 0 else 0
    progress_bar = "[" + "🟢" * (math.floor(percentage / 10)) + "⚫" * (10 - math.floor(percentage / 10)) + "]"
    
    current_status = (
        f"**{status_msg} {filename}** {round(percentage, 2)}%\n"
        f"{progress_bar}\n"
        f"**Speed**: {humanize.naturalsize(speed)}/s\n"
        f"**Downloaded**: {humanize.naturalsize(current)} / {humanize.naturalsize(total)}\n"
        f"**Time Left**: {humanize.naturaldelta(remaining_time)}"
    )
    
    try:
        await msg.edit_text(current_status)
    except pyrogram.errors.MessageNotModified:
        pass

# Command: /compress - Compress files
@bot.on_message(filters.command("compress"))
async def compress(client: Client, message: Message):
    user_id = message.from_user.id
    if is_empty(user_id):
        await message.reply_text(empty_list_msg)
        return

    dirpath = pathlib.Path(f"{user_id}/files")
    size_limit = None
    args = message.text.strip().split()
    if len(args) > 1:
        try:
            size_limit = int(args[1])
        except ValueError:
            await message.reply_text("Invalid size limit. Please provide a valid integer.")

    # Ask for a new file name
    file_name_msg = await client.ask(user_id, "Enter the name for the compressed file (without extension):")
    new_file_name = file_name_msg.text.strip()

    # Ask if a password should be added
    password_msg = await client.ask(user_id, "Enter a password for the zip file, or send 'NO' if no password is required:")
    password = password_msg.text.strip()
    password = None if password.lower() == 'no' else password

    await message.reply_text(f"Compressing files into {new_file_name}.zip...")

    zip_dir = zip_files(dirpath, size_limit, new_file_name, password)
    await message.reply_text("Compression complete!")

    # Upload compressed files
    await upload_files(user_id, zip_dir)

# Helper function to zip files
def zip_files(dirpath: pathlib.Path, size_limit: int, new_file_name: str, password: str):
    import zipfile
    from zipfile import ZipFile

    # Create the output directory for the compressed file
    zip_dir = pathlib.Path(f"{dirpath.parent}/compressed")
    zip_dir.mkdir(parents=True, exist_ok=True)

    # Create the zip file
    zip_path = zip_dir / f"{new_file_name}.zip"
    
    with ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in dirpath.iterdir():
            zipf.write(file, arcname=file.name)

    # If a password is provided, apply it (this requires a separate library like `pyminizip`)
    if password:
        import pyminizip
        compressed_with_password = zip_dir / f"{new_file_name}_password_protected.zip"
        pyminizip.compress(str(zip_path), None, str(compressed_with_password), password, 5)
        zip_path.unlink()  # Remove the non-password protected version
        return compressed_with_password

    return zip_path

# Function to upload files after compression
async def upload_files(user_id: int, zip_dir: pathlib.Path):
    progress_message = await bot.send_message(user_id, "📤 Uploading compressed files...")
    
    start_time = time.time()
    for file in sorted(zip_dir.iterdir()):
        try:
            await bot.send_document(
                chat_id=user_id,
                document=str(file),
                caption=f"Uploaded: {file.name}",
                progress=update_progress_bar,
                progress_args=("📤 Uploading", start_time, progress_message, file.name)
            )
        except Exception as e:
            await bot.send_message(user_id, f"Failed to upload {file.name}: {str(e)}")
    
    shutil.rmtree(str(zip_dir))  # Clean up after upload
    await progress_message.delete()

# Command: /link - Generate a download link
@bot.on_message(filters.command("link"))
async def generate_link(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Please reply to a file to generate a link.")
        return

    replied_message = message.reply_to_message

    # Check if the message contains media that can be downloaded
    media = None
    media_types = ["document", "video", "audio", "photo"]
    for media_type in media_types:
        media = getattr(replied_message, media_type, None)
        if media:
            break

    if not media:
        await message.reply_text("No downloadable media found in the replied message.")
        return

    user_id = message.from_user.id
    dirpath = pathlib.Path(f"{user_id}/files")
    dirpath.mkdir(parents=True, exist_ok=True)

    # Generate a file name
    if isinstance(media, pyrogram.types.Photo):
        filename = f"{media.file_unique_id}.jpg"
    else:
        filename = media.file_name or f"{media.file_unique_id}{mimetypes.guess_extension(media.mime_type) or ''}"

    filepath = dirpath / filename

    # Download the file if not already available locally
    if not filepath.exists():
        progress_msg = await message.reply_text("📥 Downloading file...")
        try:
            await replied_message.download(
                file_name=str(filepath),
                progress=update_progress_bar,
                progress_args=("📥 Downloading", time.time(), progress_msg, filename)
            )
            await progress_msg.delete()
        except Exception as e:
            await progress_msg.edit_text(f"Failed to download file: {str(e)}")
            return

    # Instead of using relative_to, construct the link directly
    file_url = f"http://{get_local_ip()}:{8000}/{filepath.as_posix()}"
    await message.reply_text(f"Here is your download link:\n{file_url}")

# Entry point for the bot
async def start():
    print("Bot is running...")
    await bot.send_message(MESSAGE_CHANNEL_ID, "Bot has started.")

if __name__ == "__main__":
    bot.start()
    asyncio.get_event_loop().run_until_complete(start())
    idle()
