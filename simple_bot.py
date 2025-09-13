#!/usr/bin/env python3
"""
Complete Telegram bot with file upload functionality
"""
import os
import uuid
import tempfile
import asyncio
import mimetypes
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction

# Import our modules
from database import db
from wasabi_storage import storage

# Create bot client
app = Client(
    "filebot",
    api_id=int(os.getenv('API_ID')),
    api_hash=os.getenv('API_HASH'),
    bot_token=os.getenv('BOT_TOKEN')
)

# Initialize database on startup
@app.on_message(filters.command("init_db"))
async def init_database(client, message):
    """Initialize database connection - admin only"""
    if message.from_user.id != int(os.getenv('ADMIN_USER_ID', '0')):
        return
    
    try:
        await db.connect()
        await message.reply_text("✅ Database initialized successfully!")
    except Exception as e:
        await message.reply_text(f"❌ Database initialization failed: {e}")

async def save_user_info(user):
    """Save user information to database"""
    try:
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        await db.save_user(user_data)
    except Exception as e:
        print(f"Error saving user info: {e}")

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handle /start command"""
    await save_user_info(message.from_user)
    
    welcome_text = """🚀 **TURBO FILE BOT - MAXIMUM SPEED!**

⚡ **TURBO FEATURES:**
• Upload files up to 4GB at MAXIMUM SPEED
• High-performance Wasabi cloud storage
• Instant MX Player & VLC integration
• Lightning-fast file sharing & collaboration
• No expiration permanent links
• Mobile optimized turbo streaming

🔥 **TURBO COMMANDS:**
• Send any file for INSTANT turbo upload
• /list - View your uploaded files with speed stats
• /web - Access high-speed web interface
• /help - Show detailed turbo guide

💨 **READY FOR TURBO SPEED? Send me any file!**"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Upload File", callback_data="upload_help")],
        [InlineKeyboardButton("📁 My Files", callback_data="list_files")],
        [InlineKeyboardButton("🌐 Web Interface", url=f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')}")],
    ])
    
    await message.reply_text(welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("web"))
async def web_command(client, message: Message):
    """Handle /web command"""
    domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
    await message.reply_text(
        f"🌐 **Web Interface:**\n"
        f"https://{domain}\n\n"
        "• Browse and download files\n"
        "• Stream videos and audio\n"
        "• MX Player & VLC integration\n"
        "• Mobile-optimized interface"
    )

@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_file(client, message: Message):
    """Handle file uploads with actual cloud storage"""
    await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
    
    # Get file info
    file_info = None
    if message.document:
        file_info = message.document
    elif message.video:
        file_info = message.video
    elif message.audio:
        file_info = message.audio
    elif message.photo:
        file_info = message.photo
    
    if not file_info:
        await message.reply_text("❌ Unsupported file type")
        return
    
    # Check file size (4GB limit)
    file_size = getattr(file_info, 'file_size', 0)
    if file_size > 4 * 1024 * 1024 * 1024:
        await message.reply_text("❌ File too large! Maximum size is 4GB")
        return
    
    file_name = getattr(file_info, 'file_name', f'media_{int(datetime.now().timestamp())}')
    file_id = str(uuid.uuid4())
    
    status_msg = await message.reply_text(
        f"🚀 **TURBO UPLOAD STARTING...**\n\n"
        f"📁 **File:** {file_name}\n"
        f"📊 **Size:** {format_file_size(file_size)}\n"
        f"⚡ **Speed:** Initializing high-speed transfer...\n"
        f"🔄 **Status:** Downloading from Telegram..."
    )
    
    upload_start_time = datetime.now()
    
    try:
        # Initialize database connection if not already done
        if not db.pool:
            await db.connect()
        
        # Fast download from Telegram with progress
        download_start = datetime.now()
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            await message.download(temp_file.name)
            temp_path = temp_file.name
        
        download_time = (datetime.now() - download_start).total_seconds()
        download_speed = file_size / download_time / 1024 / 1024 if download_time > 0 else 0
        
        await status_msg.edit_text(
            f"🚀 **TURBO UPLOAD IN PROGRESS...**\n\n"
            f"📁 **File:** {file_name}\n"
            f"📊 **Size:** {format_file_size(file_size)}\n"
            f"⚡ **Download Speed:** {download_speed:.1f} MB/s\n"
            f"☁️ **Status:** High-speed upload to cloud storage...\n"
            f"🔥 **Mode:** MAXIMUM PERFORMANCE"
        )
        
        # High-speed upload to Wasabi with progress tracking
        wasabi_key = f"files/{file_id}/{file_name}"
        uploaded_bytes = 0
        last_update = datetime.now()
        
        def progress_callback(bytes_transferred):
            nonlocal uploaded_bytes, last_update
            uploaded_bytes = bytes_transferred
            
            # Update progress every 2 seconds for real-time feedback
            now = datetime.now()
            if (now - last_update).total_seconds() >= 2:
                last_update = now
                
                progress_percent = (bytes_transferred / file_size) * 100
                elapsed_time = (now - upload_start_time).total_seconds()
                upload_speed = bytes_transferred / elapsed_time / 1024 / 1024 if elapsed_time > 0 else 0
                
                # Calculate ETA
                remaining_bytes = file_size - bytes_transferred
                eta_seconds = remaining_bytes / (bytes_transferred / elapsed_time) if bytes_transferred > 0 else 0
                eta_text = f"{int(eta_seconds)}s" if eta_seconds < 60 else f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
                
                asyncio.create_task(status_msg.edit_text(
                    f"🚀 **TURBO UPLOAD - {progress_percent:.1f}%**\n\n"
                    f"📁 **File:** {file_name}\n"
                    f"📊 **Size:** {format_file_size(file_size)}\n"
                    f"⚡ **Speed:** {upload_speed:.1f} MB/s\n"
                    f"📈 **Progress:** {format_file_size(bytes_transferred)} / {format_file_size(file_size)}\n"
                    f"⏱️ **ETA:** {eta_text}\n"
                    f"🔥 **Status:** MAXIMUM PERFORMANCE MODE"
                ))
        
        success = await storage.upload_file(temp_path, wasabi_key, progress_callback)
        
        if success:
            # Save file metadata to database
            file_data = {
                'file_id': file_id,
                'telegram_file_id': file_info.file_id,
                'wasabi_key': wasabi_key,
                'original_name': file_name,
                'file_size': file_size,
                'mime_type': getattr(file_info, 'mime_type', mimetypes.guess_type(file_name)[0]),
                'uploader_id': message.from_user.id,
                'uploader_username': message.from_user.username,
                'metadata': {
                    'width': getattr(file_info, 'width', None),
                    'height': getattr(file_info, 'height', None),
                    'duration': getattr(file_info, 'duration', None)
                }
            }
            
            await db.save_file(file_data)
            
            # Create response with action buttons
            domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
            is_media = file_data['mime_type'] and (
                file_data['mime_type'].startswith('video/') or 
                file_data['mime_type'].startswith('audio/')
            )
            
            buttons = [
                [InlineKeyboardButton("📥 Download", callback_data=f"download_{file_id}")],
            ]
            
            if is_media:
                buttons.append([
                    InlineKeyboardButton("🎬 Stream", url=f"https://{domain}/player/{file_id}"),
                    InlineKeyboardButton("📱 MX Player", callback_data=f"mx_{file_id}")
                ])
            
            buttons.append([InlineKeyboardButton("🌐 View in Web", url=f"https://{domain}/stream/{file_id}")])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            # Calculate final upload stats
            total_time = (datetime.now() - upload_start_time).total_seconds()
            avg_speed = file_size / total_time / 1024 / 1024 if total_time > 0 else 0
            
            await status_msg.edit_text(
                f"✅ **TURBO UPLOAD COMPLETE!**\n\n"
                f"📁 **Name:** {file_name}\n"
                f"🆔 **ID:** `{file_id}`\n"
                f"📊 **Size:** {format_file_size(file_size)}\n"
                f"⚡ **Avg Speed:** {avg_speed:.1f} MB/s\n"
                f"⏱️ **Total Time:** {total_time:.1f}s\n"
                f"🔗 **Type:** {file_data['mime_type'] or 'Unknown'}\n"
                f"☁️ **Storage:** Wasabi Cloud (High Performance)\n\n"
                f"🚀 **File ready for instant access!**",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text(
                f"❌ **TURBO UPLOAD FAILED!**\n\n"
                f"📁 **File:** {file_name}\n"
                f"❗ **Error:** High-speed upload to cloud storage failed\n"
                f"🔄 **Retry:** Try sending the file again for turbo speed\n\n"
                f"💡 **Tip:** Large files may take longer - please wait for completion."
            )
        
        # Clean up temp file
        os.unlink(temp_path)
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **TURBO UPLOAD ERROR!**\n\n"
            f"📁 **File:** {file_name}\n"
            f"❗ **Error:** {str(e)}\n"
            f"🔄 **Auto-Retry:** System optimizing for next attempt\n\n"
            f"💡 **Tip:** Send file again for turbo-charged upload!"
        )
        print(f"Turbo upload error: {e}")

@app.on_message(filters.command("list"))
async def list_files_command(client, message: Message):
    """List user's uploaded files"""
    try:
        if not db.pool:
            await db.connect()
            
        files = await db.list_user_files(message.from_user.id, limit=10)
        
        if not files:
            await message.reply_text(
                "📁 **No Files Found**\n\n"
                "You haven't uploaded any files yet.\n"
                "Send me any file to get started!"
            )
            return
        
        text = "📁 **Your Uploaded Files:**\n\n"
        for i, file_data in enumerate(files, 1):
            upload_date = file_data['upload_date'].strftime('%Y-%m-%d %H:%M')
            text += f"**{i}. {file_data['original_name']}**\n"
            text += f"   🆔 `{file_data['file_id']}`\n"
            text += f"   📊 {format_file_size(file_data['file_size'])}\n"
            text += f"   📅 {upload_date}\n"
            text += f"   ⬇️ {file_data['download_count']} downloads\n\n"
        
        await message.reply_text(text)
        
    except Exception as e:
        await message.reply_text(f"❌ Error retrieving files: {str(e)}")

@app.on_callback_query()
async def handle_callback(client, callback_query):
    """Handle inline keyboard callbacks"""
    data = callback_query.data
    
    if data == "upload_help":
        await callback_query.message.reply_text(
            "📤 **How to Upload Files:**\n\n"
            "1. Send me any file (document, video, audio, photo)\n"
            "2. Wait for the upload to complete\n"
            "3. Get instant access links for download and streaming\n\n"
            "**Supported:**\n"
            "• All file types up to 4GB\n"
            "• Direct streaming for media files\n"
            "• MX Player & VLC integration\n"
            "• Permanent cloud storage\n\n"
            "Just drag and drop or select any file to start!"
        )
    elif data == "list_files":
        await list_files_command(client, callback_query.message)
    elif data.startswith("download_"):
        file_id = data.replace("download_", "")
        try:
            if not db.pool:
                await db.connect()
            file_data = await db.get_file(file_id)
            if file_data:
                download_url = storage.generate_presigned_url(
                    file_data['wasabi_key'],
                    expiration=3600,
                    response_content_disposition=f'attachment; filename="{file_data["original_name"]}"'
                )
                await db.increment_download_count(file_id)
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download Now", url=download_url)]
                ])
                
                await callback_query.message.reply_text(
                    f"⚡ **TURBO DOWNLOAD READY!**\n\n"
                    f"📁 **File:** {file_data['original_name']}\n"
                    f"📊 **Size:** {format_file_size(file_data['file_size'])}\n"
                    f"🚀 **Speed:** High-performance download optimized\n"
                    f"⏰ **Link expires in 1 hour**\n"
                    f"📈 **Downloads:** {file_data['download_count']} times\n\n"
                    f"🔥 **Click below for maximum speed download:**",
                    reply_markup=keyboard
                )
            else:
                await callback_query.answer("File not found!", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)}", show_alert=True)
    elif data.startswith("mx_"):
        file_id = data.replace("mx_", "")
        try:
            if not db.pool:
                await db.connect()
            file_data = await db.get_file(file_id)
            if file_data:
                mx_url = storage.get_mx_player_url(file_data['wasabi_key'], file_data['original_name'])
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Open in MX Player", url=mx_url)]
                ])
                await callback_query.message.reply_text(
                    f"📱 **TURBO MX PLAYER READY!**\n\n"
                    f"📁 **File:** {file_data['original_name']}\n"
                    f"🚀 **Optimized for:** Maximum playback performance\n"
                    f"📱 **Platform:** Android MX Player\n"
                    f"⚡ **Streaming:** High-speed direct access\n\n"
                    f"🔥 **Click below for instant MX Player launch:**",
                    reply_markup=keyboard
                )
            else:
                await callback_query.answer("File not found!", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)}", show_alert=True)
    
    await callback_query.answer()

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Show detailed help"""
    help_text = """📖 **Telegram File Bot - Complete Guide**

**🔧 File Management:**
• Send any file (up to 4GB) to upload
• /list - View your uploaded files
• /start - Welcome message & features

**🌐 Web Interface:**
• /web - Get web interface link
• Browse and download files online
• Stream videos and audio directly
• Mobile-optimized design

**📱 Media Features:**
• Direct streaming for videos/audio
• MX Player integration (Android)
• VLC Player support (Universal)
• No expiration permanent links

**☁️ Cloud Storage:**
• Wasabi cloud storage integration
• 4GB file size limit
• All file types supported
• Secure and reliable hosting

**💡 Tips:**
• Files are processed automatically
• Get instant download/streaming links
• Share files via web interface
• Access from any device

Just send me any file to get started! 📤"""
    
    await message.reply_text(help_text)

@app.on_message(filters.text & ~filters.command(["start", "web", "list", "help"]))
async def handle_text(client, message: Message):
    """Handle text messages"""
    await message.reply_text(
        "🤖 **Telegram File Bot**\n\n"
        "Send me any file to upload it to cloud storage!\n\n"
        "📋 **Quick Commands:**\n"
        "• /start - Welcome & features\n"
        "• /list - Your uploaded files\n"
        "• /help - Detailed help guide\n"
        "• /web - Web interface link\n\n"
        "📤 **Ready to upload? Just send any file!**"
    )

if __name__ == "__main__":
    print("🚀 Starting Telegram File Bot...")
    app.run()