import boto3
import aiofiles
import asyncio
from botocore.config import Config
from typing import Optional, BinaryIO, AsyncIterator
import os
from datetime import datetime, timedelta

class WasabiStorage:
    def __init__(self):
        self.access_key = os.getenv('WASABI_ACCESS_KEY')
        self.secret_key = os.getenv('WASABI_SECRET_KEY')
        self.bucket_name = os.getenv('WASABI_BUCKET')
        self.region = os.getenv('WASABI_REGION', 'us-east-1')
        
        # Wasabi endpoint URL
        endpoint_url = f"https://s3.{self.region}.wasabisys.com"
        
        self.config = Config(
            region_name=self.region,
            retries={'max_attempts': 3},
            max_pool_connections=100,  # Increased for faster transfers
            read_timeout=300,  # 5 minutes for large files
            connect_timeout=60,
            tcp_keepalive=True
        )
        
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=self.config
        )
    
    async def test_connection(self) -> bool:
        """Test Wasabi connection"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.client.head_bucket(Bucket=self.bucket_name)
            )
            return True
        except Exception as e:
            print(f"Wasabi connection test failed: {e}")
            return False
    
    async def upload_file(self, file_path: str, key: str, 
                         progress_callback=None) -> bool:
        """Fast chunked upload to Wasabi storage"""
        try:
            import os
            file_size = os.path.getsize(file_path)
            
            # Use multipart upload for files larger than 100MB for better speed
            if file_size > 100 * 1024 * 1024:
                return await self._multipart_upload(file_path, key, progress_callback)
            else:
                return await self._single_upload(file_path, key, progress_callback)
                
        except Exception as e:
            print(f"Upload failed: {e}")
            return False
    
    async def _single_upload(self, file_path: str, key: str, progress_callback=None):
        """Fast single file upload"""
        def upload_callback(bytes_transferred):
            if progress_callback:
                progress_callback(bytes_transferred)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            lambda: self.client.upload_file(
                file_path, 
                self.bucket_name, 
                key,
                Callback=upload_callback,
                ExtraArgs={'StorageClass': 'STANDARD'}
            )
        )
        return True
    
    async def _multipart_upload(self, file_path: str, key: str, progress_callback=None):
        """High-speed multipart upload for large files"""
        import os
        from concurrent.futures import ThreadPoolExecutor
        
        file_size = os.path.getsize(file_path)
        chunk_size = 100 * 1024 * 1024  # 100MB chunks for maximum speed
        
        # Initialize multipart upload
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                StorageClass='STANDARD'
            )
        )
        upload_id = response['UploadId']
        
        try:
            parts = []
            uploaded_bytes = 0
            
            with open(file_path, 'rb') as f:
                part_number = 1
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Upload chunk asynchronously
                    response = await loop.run_in_executor(
                        None,
                        lambda c=chunk, pn=part_number: self.client.upload_part(
                            Bucket=self.bucket_name,
                            Key=key,
                            PartNumber=pn,
                            UploadId=upload_id,
                            Body=c
                        )
                    )
                    
                    parts.append({
                        'ETag': response['ETag'],
                        'PartNumber': part_number
                    })
                    
                    uploaded_bytes += len(chunk)
                    if progress_callback:
                        progress_callback(uploaded_bytes)
                    
                    part_number += 1
            
            # Complete multipart upload
            await loop.run_in_executor(
                None,
                lambda: self.client.complete_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={'Parts': parts}
                )
            )
            
            return True
            
        except Exception as e:
            # Abort failed upload
            await loop.run_in_executor(
                None,
                lambda: self.client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    UploadId=upload_id
                )
            )
            raise e
    
    async def upload_stream(self, stream: BinaryIO, key: str, 
                           content_type: str = None) -> bool:
        """Upload from stream to Wasabi storage"""
        try:
            loop = asyncio.get_event_loop()
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            await loop.run_in_executor(
                None, 
                self.client.upload_fileobj, 
                stream, self.bucket_name, key, extra_args
            )
            return True
        except Exception as e:
            print(f"Stream upload failed: {e}")
            return False
    
    async def download_file(self, key: str, file_path: str,
                           progress_callback=None) -> bool:
        """Download file from Wasabi storage"""
        try:
            def download_callback(bytes_transferred):
                if progress_callback:
                    progress_callback(bytes_transferred)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._download_file_sync,
                key, file_path, download_callback
            )
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False
    
    def _download_file_sync(self, key: str, file_path: str, callback=None):
        """Synchronous file download with progress callback"""
        self.client.download_file(
            self.bucket_name,
            key,
            file_path,
            Callback=callback
        )
    
    async def get_download_stream(self, key: str) -> Optional[BinaryIO]:
        """Get download stream for a file"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.client.get_object,
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body']
        except Exception as e:
            print(f"Failed to get download stream: {e}")
            return None
    
    def generate_presigned_url(self, key: str, expiration: int = 3600,
                              response_content_disposition: str = None) -> str:
        """Generate high-speed presigned URL for file access"""
        try:
            params = {
                'Bucket': self.bucket_name,
                'Key': key
            }
            
            if response_content_disposition:
                params['ResponseContentDisposition'] = response_content_disposition
            
            # Add cache control for faster downloads
            params['ResponseCacheControl'] = 'max-age=31536000'  # 1 year cache
            
            url = self.client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"Failed to generate presigned URL: {e}")
            return ""
    
    def generate_streaming_url(self, key: str, expiration: int = 86400) -> str:
        """Generate high-performance streaming URL"""
        try:
            params = {
                'Bucket': self.bucket_name,
                'Key': key,
                'ResponseCacheControl': 'max-age=86400',  # 24 hour cache
                'ResponseContentType': 'application/octet-stream'
            }
            
            url = self.client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"Failed to generate streaming URL: {e}")
            return self.generate_presigned_url(key, expiration)
    
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from Wasabi storage"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.client.delete_object,
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except Exception as e:
            print(f"Delete failed: {e}")
            return False
    
    async def get_file_info(self, key: str) -> Optional[dict]:
        """Get file metadata from Wasabi"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.client.head_object,
                Bucket=self.bucket_name,
                Key=key
            )
            return {
                'size': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag')
            }
        except Exception as e:
            print(f"Failed to get file info: {e}")
            return None
    
    def get_mx_player_url(self, key: str, filename: str) -> str:
        """Generate MX Player compatible URL"""
        streaming_url = self.generate_streaming_url(key, 86400)  # 24 hour expiry
        # MX Player URL scheme
        mx_url = f"intent:{streaming_url}#Intent;package=com.mxtech.videoplayer.ad;end"
        return mx_url
    
    def get_vlc_url(self, key: str) -> str:
        """Generate VLC compatible URL"""
        streaming_url = self.generate_streaming_url(key, 86400)  # 24 hour expiry
        # VLC URL scheme
        vlc_url = f"vlc://{streaming_url}"
        return vlc_url

# Global storage instance
storage = WasabiStorage()