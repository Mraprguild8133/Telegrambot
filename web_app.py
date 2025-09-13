from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiofiles
import os
from typing import Optional
import mimetypes

from database import db
from wasabi_storage import storage

app = FastAPI(title="Telegram File Bot Web Interface")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    await db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await db.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    """Files listing page"""
    return templates.TemplateResponse("files.html", {"request": request})

@app.get("/d/{link_id}")
async def download_by_link(link_id: str):
    """Download file using temporary link"""
    file_data = await db.get_file_by_download_link(link_id)
    
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found or link expired")
    
    # Increment link access count
    await db.increment_link_access(link_id)
    
    # Generate download URL
    download_url = storage.generate_presigned_url(
        file_data['wasabi_key'],
        expiration=3600,
        response_content_disposition=f'attachment; filename="{file_data["original_name"]}"'
    )
    
    return RedirectResponse(url=download_url)

@app.get("/stream/{file_id}")
async def stream_file(file_id: str):
    """Stream file directly"""
    file_data = await db.get_file(file_id)
    
    if not file_data or not file_data['is_public']:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Generate streaming URL
    streaming_url = storage.generate_streaming_url(file_data['wasabi_key'])
    
    return RedirectResponse(url=streaming_url)

@app.get("/player/{file_id}")
async def player_page(request: Request, file_id: str):
    """Video player page"""
    file_data = await db.get_file(file_id)
    
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file is video/audio
    if not (file_data['mime_type'] and 
            (file_data['mime_type'].startswith('video/') or 
             file_data['mime_type'].startswith('audio/'))):
        raise HTTPException(status_code=400, detail="File is not playable")
    
    streaming_url = storage.generate_streaming_url(file_data['wasabi_key'])
    mx_url = storage.get_mx_player_url(file_data['wasabi_key'], file_data['original_name'])
    vlc_url = storage.get_vlc_url(file_data['wasabi_key'])
    
    return templates.TemplateResponse("player.html", {
        "request": request,
        "file": file_data,
        "streaming_url": streaming_url,
        "mx_url": mx_url,
        "vlc_url": vlc_url
    })

@app.get("/api/files")
async def api_list_files(limit: int = 50, offset: int = 0, search: str = ""):
    """API endpoint to list public files"""
    if search:
        files = await db.search_files(search, limit=limit)
    else:
        files = await db.search_files("", limit=limit)
    return {"files": files}

@app.get("/api/file/{file_id}")
async def api_get_file(file_id: str):
    """API endpoint to get file metadata"""
    file_data = await db.get_file(file_id)
    
    if not file_data or not file_data['is_public']:
        raise HTTPException(status_code=404, detail="File not found")
    
    return file_data

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "telegram-file-bot"}