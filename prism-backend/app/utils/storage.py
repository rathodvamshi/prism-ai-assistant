"""Storage abstraction for Cloudinary or AWS S3.

Usage:
  from app.utils.storage import storage_client
  await storage_client.upload_file(file_path, key)
"""
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

STORAGE_PROVIDER = os.getenv('STORAGE_PROVIDER', 's3').lower()  # 's3' or 'cloudinary'


class StorageClient:
    def __init__(self):
        self.provider = STORAGE_PROVIDER
        if self.provider == 'cloudinary':
            try:
                import cloudinary
                import cloudinary.uploader
                cloudinary.config(
                    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                    api_key=os.getenv('CLOUDINARY_API_KEY'),
                    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                    secure=True
                )
                self.client = cloudinary
                logger.info('Cloudinary storage initialized')
            except Exception as e:
                logger.error(f'Failed to initialize Cloudinary: {e}')
                raise
        else:
            # Default to S3
            try:
                import boto3
                self.s3 = boto3.client(
                    's3',
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                    region_name=os.getenv('AWS_REGION')
                )
                self.bucket = os.getenv('AWS_S3_BUCKET')
                logger.info('S3 storage initialized')
            except Exception as e:
                logger.error(f'Failed to initialize S3 client: {e}')
                raise

    async def upload_file(self, file_path: str, key: str, public: bool = True) -> Optional[str]:
        """Upload file and return public URL (or None).

        Note: This is a thin wrapper; callers should handle errors accordingly.
        """
        if self.provider == 'cloudinary':
            try:
                result = self.client.uploader.upload(file_path, public_id=key, overwrite=True)
                return result.get('secure_url')
            except Exception as e:
                logger.error(f'Cloudinary upload failed: {e}')
                return None
        else:
            try:
                extra_args = {'ACL': 'public-read'} if public else {}
                self.s3.upload_file(file_path, self.bucket, key, ExtraArgs=extra_args)
                region = os.getenv('AWS_REGION') or 'us-east-1'
                url = f'https://{self.bucket}.s3.{region}.amazonaws.com/{key}'
                return url
            except Exception as e:
                logger.error(f'S3 upload failed: {e}')
                return None


# Singleton instance
storage_client = StorageClient()
