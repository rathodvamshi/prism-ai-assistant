# Cloud Storage (S3 or Cloudinary)

This project uses `app.utils.storage.StorageClient` to abstract uploads.

Configure via environment variables in Railway:
- `STORAGE_PROVIDER` = `s3` or `cloudinary`

If using S3 (recommended for large files):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET`
- `AWS_REGION`

If using Cloudinary (simple image/video hosting):
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Usage example (server-side):
```python
from app.utils.storage import storage_client
url = await storage_client.upload_file('/tmp/upload.jpg', 'uploads/12345.jpg')
```
