
import boto3
from django.conf import settings
import uuid
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class DocumentService:
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def upload_document(self, file, case_id: str) -> str:
        """
        Upload document to S3 and return file path
        From: Development Guide PDF
        """
        try:
            # Generate unique filename
            file_extension = file.name.split('.')[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = f"cases/{case_id}/documents/{unique_filename}"
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                file_path,
                ExtraArgs={
                    'ACL': 'private',
                    'ContentType': file.content_type,
                    'Metadata': {
                        'case_id': case_id,
                        'original_filename': file.name
                    }
                }
            )
            
            logger.info(f"✓ Document uploaded: {file_path}")
            return file_path
        
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise Exception(f"Failed to upload document: {str(e)}")
    
    def get_presigned_url(self, file_path: str, expiration: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_path
                },
                ExpiresIn=expiration
            )
            return url
        
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
    
    def delete_document(self, file_path: str) -> bool:
        """Delete document from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            logger.info(f"✓ Document deleted: {file_path}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def download_document(self, file_path: str, local_path: str) -> bool:
        """Download document from S3 to local filesystem"""
        try:
            self.s3_client.download_file(
                self.bucket_name,
                file_path,
                local_path
            )
            logger.info(f"✓ Document downloaded: {file_path} -> {local_path}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to download document: {e}")
            return False
    
    def list_documents(self, case_id: str) -> list:
        """List all documents for a case"""
        try:
            prefix = f"cases/{case_id}/documents/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            documents = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    documents.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': self.get_presigned_url(obj['Key'])
                    })
            
            return documents
        
        except ClientError as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
    def get_document_metadata(self, file_path: str) -> dict:
        """Get document metadata from S3"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            
            return {
                'size': response['ContentLength'],
                'content_type': response['ContentType'],
                'last_modified': response['LastModified'],
                'metadata': response.get('Metadata', {})
            }
        
        except ClientError as e:
            logger.error(f"Failed to get document metadata: {e}")
            return {}