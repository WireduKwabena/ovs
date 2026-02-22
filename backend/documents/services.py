from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    boto3 = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


logger = logging.getLogger(__name__)


class DocumentServiceError(RuntimeError):
    """Raised when S3 document operations fail."""


class DocumentService:
    """S3-backed document helper service."""

    def __init__(self):
        if not getattr(settings, "USE_S3", False):
            raise DocumentServiceError("DocumentService requires USE_S3=True.")
        if boto3 is None:
            raise DocumentServiceError("boto3 is not installed. Install boto3 to use DocumentService.")

        bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        if not bucket_name:
            raise DocumentServiceError("AWS_STORAGE_BUCKET_NAME is required for DocumentService.")

        client_kwargs: dict[str, Any] = {}
        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        region_name = getattr(settings, "AWS_S3_REGION_NAME", "")

        if access_key:
            client_kwargs["aws_access_key_id"] = access_key
        if secret_key:
            client_kwargs["aws_secret_access_key"] = secret_key
        if region_name:
            client_kwargs["region_name"] = region_name

        try:
            self.s3_client = boto3.client("s3", **client_kwargs)
        except Exception as exc:  # pragma: no cover - depends on boto/runtime setup
            raise DocumentServiceError(f"Failed to initialize S3 client: {exc}") from exc
        self.bucket_name = bucket_name

    @staticmethod
    def _normalize_required(value: Any, field_name: str) -> str:
        normalized = str(value).strip() if value is not None else ""
        if not normalized:
            raise DocumentServiceError(f"{field_name} is required.")
        return normalized

    def upload_document(self, file, case_id: str) -> str:
        """Upload a document object to S3 and return the object key."""
        normalized_case_id = self._normalize_required(case_id, "case_id")
        filename = getattr(file, "name", "")
        if not filename:
            raise DocumentServiceError("Upload file must have a valid filename.")

        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        unique_filename = f"{uuid.uuid4()}.{ext}"
        file_path = f"cases/{normalized_case_id}/documents/{unique_filename}"
        content_type = getattr(file, "content_type", None) or "application/octet-stream"

        try:
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                file_path,
                ExtraArgs={
                    "ACL": "private",
                    "ContentType": content_type,
                    "Metadata": {
                        "case_id": normalized_case_id,
                        "original_filename": filename,
                    },
                },
            )
        except (ClientError, BotoCoreError) as exc:
            logger.exception("S3 upload failed for case=%s filename=%s", normalized_case_id, filename)
            raise DocumentServiceError(f"Failed to upload document: {exc}") from exc

        logger.info("Document uploaded to S3: %s", file_path)
        return file_path

    def get_presigned_url(self, file_path: str, expiration: int = 3600) -> str | None:
        """Generate a temporary presigned URL for document download."""
        try:
            normalized_path = self._normalize_required(file_path, "file_path")
        except DocumentServiceError:
            logger.warning("Cannot generate presigned URL: file_path is required.")
            return None

        if expiration <= 0:
            logger.warning("Cannot generate presigned URL: expiration must be > 0.")
            return None

        try:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": normalized_path},
                ExpiresIn=expiration,
            )
        except (ClientError, BotoCoreError):
            logger.exception("Failed to generate presigned URL for key=%s", normalized_path)
            return None

    def delete_document(self, file_path: str) -> bool:
        """Delete a document from S3."""
        try:
            normalized_path = self._normalize_required(file_path, "file_path")
        except DocumentServiceError:
            logger.warning("Cannot delete document: file_path is required.")
            return False

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=normalized_path)
            logger.info("Document deleted from S3: %s", normalized_path)
            return True
        except (ClientError, BotoCoreError):
            logger.exception("Failed to delete S3 key=%s", normalized_path)
            return False

    def download_document(self, file_path: str, local_path: str) -> bool:
        """Download a document from S3 to a local path."""
        try:
            normalized_path = self._normalize_required(file_path, "file_path")
            normalized_local_path = self._normalize_required(local_path, "local_path")
        except DocumentServiceError:
            logger.warning("Cannot download document: file_path and local_path are required.")
            return False

        try:
            self.s3_client.download_file(self.bucket_name, normalized_path, normalized_local_path)
            logger.info("Document downloaded from S3: %s -> %s", normalized_path, normalized_local_path)
            return True
        except (ClientError, BotoCoreError):
            logger.exception("Failed to download S3 key=%s to path=%s", normalized_path, normalized_local_path)
            return False

    def list_documents(self, case_id: str) -> list[dict[str, Any]]:
        """List all documents for a case prefix."""
        try:
            normalized_case_id = self._normalize_required(case_id, "case_id")
        except DocumentServiceError:
            logger.warning("Cannot list documents: case_id is required.")
            return []

        prefix = f"cases/{normalized_case_id}/documents/"
        documents: list[dict[str, Any]] = []

        continuation_token: str | None = None
        page_count = 0
        try:
            while True:
                page_count += 1
                if page_count > 1000:
                    logger.error("Aborting S3 list for case=%s due to excessive pagination.", normalized_case_id)
                    break

                request: dict[str, Any] = {"Bucket": self.bucket_name, "Prefix": prefix}
                if continuation_token:
                    request["ContinuationToken"] = continuation_token

                response = self.s3_client.list_objects_v2(**request)
                for obj in response.get("Contents", []):
                    key = obj["Key"]
                    documents.append(
                        {
                            "key": key,
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"],
                            "url": self.get_presigned_url(key),
                        }
                    )

                if not response.get("IsTruncated"):
                    break
                next_token = response.get("NextContinuationToken")
                if not next_token:
                    logger.error(
                        "S3 response is truncated but missing NextContinuationToken for case=%s.",
                        normalized_case_id,
                    )
                    break
                continuation_token = next_token
        except (ClientError, BotoCoreError):
            logger.exception("Failed to list S3 documents for case=%s", normalized_case_id)
            return []

        return documents

    def get_document_metadata(self, file_path: str) -> dict[str, Any]:
        """Fetch metadata for a specific S3 object key."""
        try:
            normalized_path = self._normalize_required(file_path, "file_path")
        except DocumentServiceError:
            logger.warning("Cannot get metadata: file_path is required.")
            return {}

        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=normalized_path)
            return {
                "size": response["ContentLength"],
                "content_type": response["ContentType"],
                "last_modified": response["LastModified"],
                "metadata": response.get("Metadata", {}),
            }
        except (ClientError, BotoCoreError):
            logger.exception("Failed to get metadata for S3 key=%s", normalized_path)
            return {}
