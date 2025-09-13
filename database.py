import asyncpg
import asyncio
from typing import Optional, List, Dict, Any
import os
from datetime import datetime
import json

class Database:
    def __init__(self):
        self.pool = None
        self.database_url = os.getenv('DATABASE_URL')
    
    async def connect(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(self.database_url)
        await self.create_tables()
    
    async def create_tables(self):
        """Create necessary tables if they don't exist"""
        async with self.pool.acquire() as conn:
            # Files table for storing file metadata
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    file_id VARCHAR(255) UNIQUE NOT NULL,
                    telegram_file_id VARCHAR(255),
                    wasabi_key VARCHAR(255),
                    original_name VARCHAR(255),
                    file_size BIGINT,
                    mime_type VARCHAR(100),
                    uploader_id BIGINT,
                    uploader_username VARCHAR(255),
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    download_count INTEGER DEFAULT 0,
                    is_public BOOLEAN DEFAULT true,
                    description TEXT,
                    tags TEXT[],
                    metadata JSONB
                )
            """)
            
            # Shared files table for collaboration features
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shared_files (
                    id SERIAL PRIMARY KEY,
                    file_id VARCHAR(255) REFERENCES files(file_id),
                    shared_with_user_id BIGINT,
                    shared_by_user_id BIGINT,
                    permission_level VARCHAR(20) DEFAULT 'read',
                    shared_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            """)
            
            # Users table for user management
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_premium BOOLEAN DEFAULT false,
                    storage_used BIGINT DEFAULT 0,
                    storage_limit BIGINT DEFAULT 2147483648,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Download links table for temporary access
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS download_links (
                    id SERIAL PRIMARY KEY,
                    link_id VARCHAR(255) UNIQUE NOT NULL,
                    file_id VARCHAR(255) REFERENCES files(file_id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    max_access INTEGER DEFAULT -1,
                    created_by BIGINT
                )
            """)
    
    async def save_file(self, file_data: Dict[str, Any]) -> str:
        """Save file metadata to database"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO files (
                    file_id, telegram_file_id, wasabi_key, original_name, 
                    file_size, mime_type, uploader_id, uploader_username,
                    description, tags, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING file_id
            """, 
                file_data['file_id'],
                file_data.get('telegram_file_id'),
                file_data.get('wasabi_key'),
                file_data['original_name'],
                file_data['file_size'],
                file_data.get('mime_type'),
                file_data['uploader_id'],
                file_data.get('uploader_username'),
                file_data.get('description', ''),
                file_data.get('tags', []),
                json.dumps(file_data.get('metadata', {}))
            )
            return result['file_id']
    
    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by file ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM files WHERE file_id = $1", file_id
            )
            if row:
                return dict(row)
            return None
    
    async def list_user_files(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List files uploaded by a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM files 
                WHERE uploader_id = $1 
                ORDER BY upload_date DESC 
                LIMIT $2 OFFSET $3
            """, user_id, limit, offset)
            return [dict(row) for row in rows]
    
    async def search_files(self, query: str, user_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search files by name or tags"""
        async with self.pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch("""
                    SELECT * FROM files 
                    WHERE (uploader_id = $1 OR is_public = true)
                    AND (original_name ILIKE $2 OR $3 = ANY(tags))
                    ORDER BY upload_date DESC 
                    LIMIT $4
                """, user_id, f"%{query}%", query, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM files 
                    WHERE is_public = true
                    AND (original_name ILIKE $1 OR $2 = ANY(tags))
                    ORDER BY upload_date DESC 
                    LIMIT $3
                """, f"%{query}%", query, limit)
            return [dict(row) for row in rows]
    
    async def increment_download_count(self, file_id: str):
        """Increment download counter for a file"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE files SET download_count = download_count + 1 WHERE file_id = $1",
                file_id
            )
    
    async def save_user(self, user_data: Dict[str, Any]):
        """Save or update user information"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_active = CURRENT_TIMESTAMP
            """, 
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name')
            )
    
    async def share_file(self, file_id: str, shared_with_user_id: int, 
                        shared_by_user_id: int, permission: str = 'read',
                        expires_at: Optional[datetime] = None) -> int:
        """Share a file with another user"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO shared_files (
                    file_id, shared_with_user_id, shared_by_user_id, 
                    permission_level, expires_at
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, file_id, shared_with_user_id, shared_by_user_id, permission, expires_at)
            return result['id']
    
    async def get_shared_files(self, user_id: int) -> List[Dict[str, Any]]:
        """Get files shared with a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT f.*, sf.permission_level, sf.shared_date, sf.shared_by_user_id
                FROM files f
                JOIN shared_files sf ON f.file_id = sf.file_id
                WHERE sf.shared_with_user_id = $1
                AND (sf.expires_at IS NULL OR sf.expires_at > CURRENT_TIMESTAMP)
                ORDER BY sf.shared_date DESC
            """, user_id)
            return [dict(row) for row in rows]
    
    async def create_download_link(self, file_id: str, created_by: int, 
                                 expires_at: Optional[datetime] = None,
                                 max_access: int = -1) -> str:
        """Create a temporary download link"""
        import uuid
        link_id = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO download_links (
                    link_id, file_id, created_by, expires_at, max_access
                ) VALUES ($1, $2, $3, $4, $5)
            """, link_id, file_id, created_by, expires_at, max_access)
            return link_id
    
    async def get_file_by_download_link(self, link_id: str) -> Optional[Dict[str, Any]]:
        """Get file by download link ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT f.*, dl.access_count, dl.max_access, dl.expires_at as link_expires_at
                FROM files f
                JOIN download_links dl ON f.file_id = dl.file_id
                WHERE dl.link_id = $1
                AND (dl.expires_at IS NULL OR dl.expires_at > CURRENT_TIMESTAMP)
                AND (dl.max_access = -1 OR dl.access_count < dl.max_access)
            """, link_id)
            if row:
                return dict(row)
            return None
    
    async def increment_link_access(self, link_id: str):
        """Increment access count for download link"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE download_links SET access_count = access_count + 1 WHERE link_id = $1",
                link_id
            )
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()

# Global database instance
db = Database()