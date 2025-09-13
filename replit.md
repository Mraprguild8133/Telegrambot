# Telegram File Bot

## Overview
A comprehensive file storage and streaming solution combining a powerful Telegram bot with Wasabi cloud storage integration. Handles file uploads and downloads up to 4GB with cloud storage integration, MX Player support, and no expiration links.

## Recent Changes
- 2025-09-09: Created complete bot implementation with database models, Wasabi storage, web interface
- Added MX Player and VLC direct integration
- Implemented file sharing and collaboration features
- Created responsive web interface for streaming and downloads

## User Preferences
- Focus on functionality over mock data
- Prefer real integrations over placeholders
- Mobile-optimized design for streaming
- Clean, efficient code structure

## Project Architecture

### Core Components
1. **bot.py** - Main Telegram bot implementation using Pyrogram
2. **database.py** - PostgreSQL database models and operations
3. **wasabi_storage.py** - Wasabi cloud storage integration via Boto3
4. **web_app.py** - FastAPI web interface for streaming/downloads
5. **main.py** - Application entry point and service orchestration

### Database Schema
- **files** - File metadata, storage keys, permissions
- **shared_files** - File sharing and collaboration
- **users** - User management and storage limits
- **download_links** - Temporary access links

### Features Implemented
- 4GB file upload support via Telegram
- Wasabi cloud storage for reliable file hosting
- MX Player & VLC direct integration for mobile
- File sharing and collaboration system
- Web interface with responsive design
- No expiration permanent links
- Progress tracking for uploads/downloads
- Mobile-optimized streaming

### API Endpoints
- `/` - Main web interface
- `/files` - Browse public files
- `/d/{link_id}` - Download via temporary link
- `/stream/{file_id}` - Direct file streaming
- `/player/{file_id}` - Media player interface
- `/api/files` - REST API for file listing

### Bot Commands
- `/start` - Welcome and help
- `/upload` - Upload file instructions
- `/list` - List user files
- `/search` - Search files
- `/download` - Get download link
- `/stream` - Get streaming link
- `/mx` - MX Player link
- `/vlc` - VLC player link
- `/share` - Share with user
- `/shared` - View shared files
- `/link` - Create temporary link
- `/test` - Test connections

## Environment Variables
All credentials are managed via Replit Secrets:
- API_ID, API_HASH, BOT_TOKEN (Telegram)
- WASABI_ACCESS_KEY, WASABI_SECRET_KEY, WASABI_BUCKET, WASABI_REGION (Storage)
- DATABASE_URL (PostgreSQL - auto-managed)

## Current Status
- ✅ Database connected and tables created
- ⚠️ Wasabi connection needs debugging (argument error)
- ✅ Web server running on port 5000
- 🤖 Telegram bot starting up

## Next Steps
- Fix Wasabi storage connection issue
- Test complete upload/download flow
- Verify MX Player/VLC integration
- Test file sharing features