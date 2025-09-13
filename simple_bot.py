#!/usr/bin/env python3
"""
Telegram File Bot with optional Render web interface
Main: Telegram bot
Secondary: Web interface (port 5000)
"""

import os
import uuid
import tempfile
import asyncio
import mimetypes
import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction

from database import db
from wasabi_storage import storage
from web_app import app as web_app
import uvicorn

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("filebot")

# ===== ENV VARIABLES =====
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN")  # e.g., mybot.onrender.com

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing required environment variables")
    exit(1)

# ===== PYROGRAM CLIENT =====
bot = Client("filebot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ===== UTILS =====
def format_file_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f}{size_names[i]}"

async def ensure_db_connected():
    if not getattr(db, "pool", None):
        await db.connect()

async def save_user_info(user):
    if not user:
        return
    try:
        await ensure_db_connected()
        await db.save_user({
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        })
    except Exception as e:
        logger.error("Error saving user info: %s", e)

def get_domain_url(path: str = "") -> str:
    if not PUBLIC_DOMAIN:
        return None
    return f"https://{PUBLIC_DOMAIN}{path}"

# ===== BOT COMMANDS =====
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await save_user_info(message.from_user)
    welcome_text = "🚀 **TURBO FILE BOT**\n\nSend any file to upload 🚀"
    buttons = [
        [InlineKeyboardButton("📤 Upload File", callback_data="upload_help")],
        [InlineKeyboardButton("📁 My Files", callback_data="list_files")]
    ]
    domain_url = get_domain_url()
    if domain_url:
        buttons.append([InlineKeyboardButton("🌐 Web Interface", url=domain_url)])
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply_text(welcome_text, reply_markup=keyboard)

@bot.on_message(filters.command("web"))
async def web_command(client, message: Message):
    domain_url = get_domain_url()
    if domain_url:
        await message.reply_text(f"🌐 Web Interface: {domain_url}")
    else:
        await message.reply_text("Web interface not configured. Set PUBLIC_DOMAIN env variable.")

@bot.on_message(filters.command("help"))
async def help_command(client, message: Message):
    await message.reply_text(
        "📖 Send any file to upload.\n"
        "Commands:\n/start - Welcome\n/list - Your files\n/web - Web interface\n/help - This message"
    )

@bot.on_message(filters.text & ~filters.command(["start","web","list","help"]))
async def handle_text(client, message: Message):
    await message.reply_text("Send a file to upload. Use /help for commands.")

# ===== FILE HANDLER =====
@bot.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_file(client, message: Message):
    await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)

    file_info = message.document or message.video or message.audio
    if message.photo:
        file_info = message.photo[-1]

    if not file_info:
        await message.reply_text("❌ Unsupported file type")
        return

    file_size = getattr(file_info, "file_size", 0)
    if file_size > 4 * 1024 * 1024 * 1024:
        await message.reply_text("❌ File too large! Max 4GB")
        return

    file_name = getattr(file_info, "file_name", f"media_{int(datetime.now().timestamp())}")
    file_id = str(uuid.uuid4())
    status_msg = await message.reply_text(f"🚀 Starting upload: {file_name}")
    upload_start_time = datetime.now()
    temp_path = None

    try:
        await ensure_db_connected()
        temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file_name}")
        await message.download(temp_path)

        wasabi_key = f"files/{file_id}/{file_name}"
        uploaded_bytes = 0
        last_update = datetime.now()

        def progress_cb(bytes_transferred):
            nonlocal uploaded_bytes, last_update
            uploaded_bytes = bytes_transferred
            now = datetime.now()
            if (now - last_update).total_seconds() >= 2:
                last_update = now
                percent = uploaded_bytes / file_size * 100
                elapsed = (now - upload_start_time).total_seconds()
                speed = uploaded_bytes / elapsed / 1024 / 1024 if elapsed > 0 else 0
                remaining = file_size - uploaded_bytes
                eta = remaining / (uploaded_bytes / elapsed) if uploaded_bytes > 0 else 0
                eta_text = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m {int(eta%60)}s"
                asyncio.create_task(
                    status_msg.edit_text(
                        f"🚀 Uploading: {file_name}\n"
                        f"📊 {percent:.1f}%\n"
                        f"⚡ Speed: {speed:.1f} MB/s\n"
                        f"⏱ ETA: {eta_text}"
                    )
                )

        success = await storage.upload_file(temp_path, wasabi_key, progress_cb)
        if success:
            file_data = {
                "file_id": file_id,
                "telegram_file_id": file_info.file_id,
                "wasabi_key": wasabi_key,
                "original_name": file_name,
                "file_size": file_size,
                "mime_type": getattr(file_info, "mime_type", mimetypes.guess_type(file_name)[0]),
                "uploader_id": message.from_user.id,
                "uploader_username": message.from_user.username,
                "metadata": {
                    "width": getattr(file_info, "width", None),
                    "height": getattr(file_info, "height", None),
                    "duration": getattr(file_info, "duration", None)
                }
            }
            await db.save_file(file_data)

            buttons = [[InlineKeyboardButton("📥 Download", callback_data=f"download_{file_id}")]]
            domain_url = get_domain_url()
            if domain_url:
                buttons.append([
                    InlineKeyboardButton("🌐 View Web", url=f"{domain_url}/stream/{file_id}"),
                    InlineKeyboardButton("🎬 Stream", url=f"{domain_url}/player/{file_id}")
                ])
                buttons.append([InlineKeyboardButton("📱 MX Player", callback_data=f"mx_{file_id}")])
            keyboard = InlineKeyboardMarkup(buttons)

            total_time = (datetime.now() - upload_start_time).total_seconds()
            avg_speed = file_size / total_time / 1024 / 1024 if total_time > 0 else 0
            await status_msg.edit_text(
                f"✅ Upload complete: {file_name}\n"
                f"Size: {format_file_size(file_size)}\n"
                f"Avg speed: {avg_speed:.1f} MB/s",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text(f"❌ Upload failed: {file_name}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        logger.exception("Upload error")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

# ===== CALLBACKS =====
@bot.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    await callback_query.answer()
    if data == "upload_help":
        await callback_query.message.reply_text("📤 Send a file to upload. Supports documents, videos, audio, photos.")
    elif data.startswith("download_"):
        file_id = data.replace("download_", "")
        try:
            await ensure_db_connected()
            file_data = await db.get_file(file_id)
            if not file_data:
                await callback_query.answer("File not found!", show_alert=True)
                return
            download_url = storage.generate_presigned_url(file_data["wasabi_key"], expiration=3600)
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download Now", url=download_url)]])
            await callback_query.message.reply_text(f"Download {file_data['original_name']}:", reply_markup=keyboard)
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)}", show_alert=True)

# ===== RUN BOT + WEB =====
async def main():
    await asyncio.gather(
        bot.start(),
        uvicorn.run(web_app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)), log_level="info")
    )
    await bot.idle()

if __name__ == "__main__":
    print("🚀 Starting Telegram File Bot (Render.com ready)...")
    asyncio.run(main())
            
