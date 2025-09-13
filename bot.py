import asyncio
import os
import uuid
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import mimetypes

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
import aiofiles

from database import db
from wasabi_storage import storage

class TelegramFileBot:
    def __init__(self):
        self.app = Client(
            "filebot",
            api_id=os.getenv('API_ID'),
            api_hash=os.getenv('API_HASH'),
            bot_token=os.getenv('BOT_TOKEN')
        )
        
        # Register handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message: Message):
            await self.save_user_info(message.from_user)
            
            welcome_text = """
🚀 **Welcome to Telegram File Bot!**

📁 **Features:**
• Upload files up to 4GB
• Cloud storage with Wasabi
• MX Player & VLC integration
• File sharing & collaboration
• No expiration links
• Mobile optimized streaming

📋 **Commands:**
/upload - Upload a file
/list - List your files
/search <query> - Search files
/share <file_id> <user_id> - Share file
/stream <file_id> - Get streaming link
/download <file_id> - Download file
/test - Test cloud connection
/help - Show this help

Just send any file to upload it instantly!
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload File", callback_data="upload")],
                [InlineKeyboardButton("📁 My Files", callback_data="list_files")],
                [InlineKeyboardButton("🔍 Search Files", callback_data="search")],
                [InlineKeyboardButton("🔗 Shared Files", callback_data="shared_files")]
            ])
            
            await message.reply_text(welcome_text, reply_markup=keyboard)
        
        @self.app.on_message(filters.command("help"))
        async def help_command(client, message: Message):
            help_text = """
📖 **Bot Commands:**

**File Management:**
• `/upload` - Upload a file (or just send any file)
• `/list` - List all your uploaded files
• `/search <query>` - Search files by name or tags
• `/delete <file_id>` - Delete a file

**File Access:**
• `/download <file_id>` - Get download link
• `/stream <file_id>` - Get streaming link
• `/mx <file_id>` - Open in MX Player
• `/vlc <file_id>` - Open in VLC Player

**Sharing & Collaboration:**
• `/share <file_id> <user_id>` - Share file with user
• `/shared` - View files shared with you
• `/link <file_id>` - Create temporary download link

**Utilities:**
• `/test` - Test Wasabi cloud connection
• `/stats` - View your storage statistics
• `/help` - Show this help message

**File Types Supported:**
Videos, Audio, Documents, Photos, Archives
Maximum file size: 4GB
            """
            await message.reply_text(help_text)
        
        @self.app.on_message(filters.command("test"))
        async def test_command(client, message: Message):
            status_msg = await message.reply_text("🔄 Testing Wasabi connection...")
            
            if await storage.test_connection():
                await status_msg.edit_text("✅ Wasabi connection successful!")
            else:
                await status_msg.edit_text("❌ Wasabi connection failed!")
        
        @self.app.on_message(filters.command("upload"))
        async def upload_command(client, message: Message):
            await message.reply_text(
                "📤 **Upload File**\n\n"
                "Send me any file (up to 4GB) and I'll store it in the cloud!\n\n"
                "Supported formats: Videos, Audio, Documents, Photos, Archives"
            )
        
        @self.app.on_message(filters.command("list"))
        async def list_command(client, message: Message):
            await self.list_user_files(message)
        
        @self.app.on_message(filters.command("search"))
        async def search_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /search <query>")
                return
            
            query = " ".join(message.command[1:])
            await self.search_files(message, query)
        
        @self.app.on_message(filters.command("download"))
        async def download_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /download <file_id>")
                return
            
            file_id = message.command[1]
            await self.generate_download_link(message, file_id)
        
        @self.app.on_message(filters.command("stream"))
        async def stream_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /stream <file_id>")
                return
            
            file_id = message.command[1]
            await self.generate_streaming_link(message, file_id)
        
        @self.app.on_message(filters.command("mx"))
        async def mx_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /mx <file_id>")
                return
            
            file_id = message.command[1]
            await self.generate_mx_link(message, file_id)
        
        @self.app.on_message(filters.command("vlc"))
        async def vlc_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /vlc <file_id>")
                return
            
            file_id = message.command[1]
            await self.generate_vlc_link(message, file_id)
        
        @self.app.on_message(filters.command("share"))
        async def share_command(client, message: Message):
            if len(message.command) < 3:
                await message.reply_text("Usage: /share <file_id> <user_id>")
                return
            
            file_id = message.command[1]
            try:
                target_user_id = int(message.command[2])
                await self.share_file(message, file_id, target_user_id)
            except ValueError:
                await message.reply_text("Invalid user ID")
        
        @self.app.on_message(filters.command("shared"))
        async def shared_command(client, message: Message):
            await self.list_shared_files(message)
        
        @self.app.on_message(filters.command("link"))
        async def link_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply_text("Usage: /link <file_id>")
                return
            
            file_id = message.command[1]
            await self.create_temporary_link(message, file_id)
        
        @self.app.on_message(filters.document | filters.video | filters.audio | filters.photo)
        async def handle_file(client, message: Message):
            await self.process_file_upload(message)
        
        @self.app.on_callback_query()
        async def handle_callback(client, callback_query: CallbackQuery):
            data = callback_query.data
            
            if data == "upload":
                await callback_query.message.reply_text(
                    "📤 Send me any file to upload it to cloud storage!"
                )
            elif data == "list_files":
                await self.list_user_files(callback_query.message)
            elif data == "search":
                await callback_query.message.reply_text(
                    "🔍 Use: /search <query> to search files"
                )
            elif data == "shared_files":
                await self.list_shared_files(callback_query.message)
            elif data.startswith("download_"):
                file_id = data.replace("download_", "")
                await self.generate_download_link(callback_query.message, file_id)
            elif data.startswith("stream_"):
                file_id = data.replace("stream_", "")
                await self.generate_streaming_link(callback_query.message, file_id)
            elif data.startswith("mx_"):
                file_id = data.replace("mx_", "")
                await self.generate_mx_link(callback_query.message, file_id)
            elif data.startswith("vlc_"):
                file_id = data.replace("vlc_", "")
                await self.generate_vlc_link(callback_query.message, file_id)
            
            await callback_query.answer()
    
    async def save_user_info(self, user):
        """Save user information to database"""
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        await db.save_user(user_data)
    
    async def process_file_upload(self, message: Message):
        """Process file upload to cloud storage"""
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
        if hasattr(file_info, 'file_size') and file_info.file_size > 4 * 1024 * 1024 * 1024:
            await message.reply_text("❌ File too large! Maximum size is 4GB")
            return
        
        file_id = str(uuid.uuid4())
        status_msg = await message.reply_text("📤 Uploading to cloud storage...")
        
        try:
            # Download file from Telegram
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                await message.download(temp_file.name)
                temp_path = temp_file.name
            
            # Upload to Wasabi
            wasabi_key = f"files/{file_id}/{file_info.file_name or 'unnamed'}"
            
            async def progress_callback(current, total):
                progress = (current / total) * 100
                await status_msg.edit_text(f"📤 Uploading: {progress:.1f}%")
            
            success = await storage.upload_file(temp_path, wasabi_key)
            
            if success:
                # Save file metadata to database
                file_data = {
                    'file_id': file_id,
                    'telegram_file_id': file_info.file_id,
                    'wasabi_key': wasabi_key,
                    'original_name': file_info.file_name or 'unnamed',
                    'file_size': getattr(file_info, 'file_size', 0),
                    'mime_type': getattr(file_info, 'mime_type', mimetypes.guess_type(file_info.file_name or '')[0]),
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
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📥 Download", callback_data=f"download_{file_id}"),
                        InlineKeyboardButton("🎬 Stream", callback_data=f"stream_{file_id}")
                    ],
                    [
                        InlineKeyboardButton("📱 MX Player", callback_data=f"mx_{file_id}"),
                        InlineKeyboardButton("🎯 VLC", callback_data=f"vlc_{file_id}")
                    ]
                ])
                
                await status_msg.edit_text(
                    f"✅ **File uploaded successfully!**\n\n"
                    f"📁 **Name:** {file_data['original_name']}\n"
                    f"🆔 **ID:** `{file_id}`\n"
                    f"📊 **Size:** {self.format_file_size(file_data['file_size'])}\n"
                    f"🔗 **Type:** {file_data['mime_type'] or 'Unknown'}\n\n"
                    f"Use the buttons below to access your file:",
                    reply_markup=keyboard
                )
            else:
                await status_msg.edit_text("❌ Upload failed! Please try again.")
            
            # Clean up temp file
            os.unlink(temp_path)
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Upload error: {str(e)}")
    
    async def list_user_files(self, message: Message):
        """List user's uploaded files"""
        files = await db.list_user_files(message.from_user.id, limit=10)
        
        if not files:
            await message.reply_text("📁 No files found. Upload some files first!")
            return
        
        text = "📁 **Your Files:**\n\n"
        for file_data in files:
            text += f"📄 **{file_data['original_name']}**\n"
            text += f"🆔 `{file_data['file_id']}`\n"
            text += f"📊 {self.format_file_size(file_data['file_size'])}\n"
            text += f"📅 {file_data['upload_date'].strftime('%Y-%m-%d %H:%M')}\n"
            text += f"⬇️ Downloads: {file_data['download_count']}\n\n"
        
        await message.reply_text(text)
    
    async def search_files(self, message: Message, query: str):
        """Search files by name or tags"""
        files = await db.search_files(query, message.from_user.id)
        
        if not files:
            await message.reply_text(f"🔍 No files found for query: '{query}'")
            return
        
        text = f"🔍 **Search Results for '{query}':**\n\n"
        for file_data in files:
            text += f"📄 **{file_data['original_name']}**\n"
            text += f"🆔 `{file_data['file_id']}`\n"
            text += f"📊 {self.format_file_size(file_data['file_size'])}\n\n"
        
        await message.reply_text(text)
    
    async def generate_download_link(self, message: Message, file_id: str):
        """Generate download link for a file"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        # Check file ownership or public access
        if file_data['uploader_id'] != message.from_user.id and not file_data['is_public']:
            await message.reply_text("❌ Access denied!")
            return
        
        # Generate presigned URL
        download_url = storage.generate_presigned_url(
            file_data['wasabi_key'], 
            expiration=3600,
            response_content_disposition=f'attachment; filename="{file_data["original_name"]}"'
        )
        
        await db.increment_download_count(file_id)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Now", url=download_url)]
        ])
        
        await message.reply_text(
            f"📥 **Download Ready!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"📊 **Size:** {self.format_file_size(file_data['file_size'])}\n"
            f"⏰ **Link expires in 1 hour**\n\n"
            f"Click the button below to download:",
            reply_markup=keyboard
        )
    
    async def generate_streaming_link(self, message: Message, file_id: str):
        """Generate streaming link for media files"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        # Check if file is streamable
        if not file_data['mime_type'] or not (
            file_data['mime_type'].startswith('video/') or 
            file_data['mime_type'].startswith('audio/')
        ):
            await message.reply_text("❌ File is not streamable!")
            return
        
        streaming_url = storage.generate_streaming_url(file_data['wasabi_key'])
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Stream Now", url=streaming_url)]
        ])
        
        await message.reply_text(
            f"🎬 **Streaming Ready!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"🎯 **Type:** {file_data['mime_type']}\n"
            f"⏰ **Link expires in 24 hours**\n\n"
            f"Click the button below to stream:",
            reply_markup=keyboard
        )
    
    async def generate_mx_link(self, message: Message, file_id: str):
        """Generate MX Player link"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        mx_url = storage.get_mx_player_url(file_data['wasabi_key'], file_data['original_name'])
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Open in MX Player", url=mx_url)]
        ])
        
        await message.reply_text(
            f"📱 **MX Player Ready!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"Click the button to open in MX Player:",
            reply_markup=keyboard
        )
    
    async def generate_vlc_link(self, message: Message, file_id: str):
        """Generate VLC Player link"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        vlc_url = storage.get_vlc_url(file_data['wasabi_key'])
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Open in VLC", url=vlc_url)]
        ])
        
        await message.reply_text(
            f"🎯 **VLC Player Ready!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"Click the button to open in VLC:",
            reply_markup=keyboard
        )
    
    async def share_file(self, message: Message, file_id: str, target_user_id: int):
        """Share file with another user"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        if file_data['uploader_id'] != message.from_user.id:
            await message.reply_text("❌ You can only share your own files!")
            return
        
        # Create share record
        share_id = await db.share_file(
            file_id, 
            target_user_id, 
            message.from_user.id,
            permission='read'
        )
        
        await message.reply_text(
            f"✅ **File shared successfully!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"👤 **Shared with:** {target_user_id}\n"
            f"🔗 **Share ID:** {share_id}"
        )
    
    async def list_shared_files(self, message: Message):
        """List files shared with the user"""
        shared_files = await db.get_shared_files(message.from_user.id)
        
        if not shared_files:
            await message.reply_text("📁 No shared files found.")
            return
        
        text = "🔗 **Files shared with you:**\n\n"
        for file_data in shared_files:
            text += f"📄 **{file_data['original_name']}**\n"
            text += f"🆔 `{file_data['file_id']}`\n"
            text += f"👤 Shared by: {file_data['shared_by_user_id']}\n"
            text += f"📅 {file_data['shared_date'].strftime('%Y-%m-%d %H:%M')}\n\n"
        
        await message.reply_text(text)
    
    async def create_temporary_link(self, message: Message, file_id: str):
        """Create temporary download link"""
        file_data = await db.get_file(file_id)
        
        if not file_data:
            await message.reply_text("❌ File not found!")
            return
        
        if file_data['uploader_id'] != message.from_user.id:
            await message.reply_text("❌ Access denied!")
            return
        
        # Create temporary link (expires in 24 hours)
        expires_at = datetime.now() + timedelta(hours=24)
        link_id = await db.create_download_link(
            file_id, 
            message.from_user.id, 
            expires_at, 
            max_access=10
        )
        
        temp_url = f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')}/d/{link_id}"
        
        await message.reply_text(
            f"🔗 **Temporary Link Created!**\n\n"
            f"📁 **File:** {file_data['original_name']}\n"
            f"🔗 **Link:** {temp_url}\n"
            f"⏰ **Expires:** 24 hours\n"
            f"📊 **Max downloads:** 10\n\n"
            f"Share this link with anyone!"
        )
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f}{size_names[i]}"
    
    def start_bot(self):
        """Start the bot synchronously"""
        print("🚀 Starting Telegram File Bot...")
        self.app.run()
    
    async def stop(self):
        """Stop the bot"""
        await self.app.stop()
        print("🛑 Telegram File Bot stopped!")

# Global bot instance
bot = TelegramFileBot()