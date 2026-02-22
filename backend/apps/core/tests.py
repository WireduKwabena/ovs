from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from documents.services import BotoCoreError, DocumentService, DocumentServiceError


class DocumentServiceTests(SimpleTestCase):
    @override_settings(USE_S3=False)
    def test_init_requires_use_s3_enabled(self):
        with self.assertRaises(DocumentServiceError):
            DocumentService()

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="",
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_init_requires_bucket_name(self):
        with self.assertRaises(DocumentServiceError):
            DocumentService()

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_upload_document_success(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3), patch(
            "documents.services.uuid.uuid4", return_value="abc123"
        ):
            service = DocumentService()
            file_obj = SimpleUploadedFile(
                name="resume.pdf",
                content=b"binary-content",
                content_type="application/pdf",
            )
            key = service.upload_document(file_obj, case_id="CASE-001")

        self.assertEqual(key, "cases/CASE-001/documents/abc123.pdf")
        mock_client.upload_fileobj.assert_called_once()

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_upload_document_requires_case_id(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            file_obj = SimpleUploadedFile(
                name="resume.pdf",
                content=b"binary-content",
                content_type="application/pdf",
            )
            with self.assertRaises(DocumentServiceError):
                service.upload_document(file_obj, case_id=" ")

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_get_presigned_url_returns_none_on_error(self):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = BotoCoreError()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            url = service.get_presigned_url("missing/object.pdf")

        self.assertIsNone(url)

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_get_presigned_url_returns_none_for_invalid_expiration(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            url = service.get_presigned_url("cases/C1/documents/a.pdf", expiration=0)

        self.assertIsNone(url)
        mock_client.generate_presigned_url.assert_not_called()

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_list_documents_handles_pagination(self):
        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = [
            {
                "Contents": [{"Key": "cases/C1/documents/a.pdf", "Size": 10, "LastModified": "now"}],
                "IsTruncated": True,
                "NextContinuationToken": "token-2",
            },
            {
                "Contents": [{"Key": "cases/C1/documents/b.pdf", "Size": 20, "LastModified": "now"}],
                "IsTruncated": False,
            },
        ]
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            with patch.object(
                service,
                "get_presigned_url",
                side_effect=["https://example.com/a", "https://example.com/b"],
            ):
                docs = service.list_documents(case_id="C1")

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]["key"], "cases/C1/documents/a.pdf")
        self.assertEqual(docs[1]["key"], "cases/C1/documents/b.pdf")

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_list_documents_stops_when_truncated_response_has_no_next_token(self):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "cases/C1/documents/a.pdf", "Size": 10, "LastModified": "now"}],
            "IsTruncated": True,
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            with patch.object(service, "get_presigned_url", return_value="https://example.com/a"):
                docs = service.list_documents(case_id="C1")

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["key"], "cases/C1/documents/a.pdf")
        self.assertEqual(mock_client.list_objects_v2.call_count, 1)

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_delete_document_success(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            success = service.delete_document("cases/C1/documents/a.pdf")

        self.assertTrue(success)
        mock_client.delete_object.assert_called_once_with(
            Bucket="unit-test-bucket",
            Key="cases/C1/documents/a.pdf",
        )

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_delete_document_returns_false_on_error(self):
        mock_client = MagicMock()
        mock_client.delete_object.side_effect = BotoCoreError()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            success = service.delete_document("cases/C1/documents/missing.pdf")

        self.assertFalse(success)

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_delete_document_returns_false_for_blank_file_path(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            success = service.delete_document(" ")

        self.assertFalse(success)
        mock_client.delete_object.assert_not_called()

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_download_document_success(self):
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            success = service.download_document(
                file_path="cases/C1/documents/a.pdf",
                local_path="/tmp/a.pdf",
            )

        self.assertTrue(success)
        mock_client.download_file.assert_called_once_with(
            "unit-test-bucket",
            "cases/C1/documents/a.pdf",
            "/tmp/a.pdf",
        )

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_download_document_returns_false_on_error(self):
        mock_client = MagicMock()
        mock_client.download_file.side_effect = BotoCoreError()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            success = service.download_document(
                file_path="cases/C1/documents/missing.pdf",
                local_path="/tmp/missing.pdf",
            )

        self.assertFalse(success)

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_get_document_metadata_success(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 512,
            "ContentType": "application/pdf",
            "LastModified": "2026-02-22T00:00:00Z",
            "Metadata": {"case_id": "C1"},
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            metadata = service.get_document_metadata("cases/C1/documents/a.pdf")

        self.assertEqual(metadata["size"], 512)
        self.assertEqual(metadata["content_type"], "application/pdf")
        self.assertEqual(metadata["metadata"], {"case_id": "C1"})
        mock_client.head_object.assert_called_once_with(
            Bucket="unit-test-bucket",
            Key="cases/C1/documents/a.pdf",
        )

    @override_settings(
        USE_S3=True,
        AWS_STORAGE_BUCKET_NAME="unit-test-bucket",
        AWS_ACCESS_KEY_ID="key",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_REGION_NAME="us-east-1",
    )
    def test_get_document_metadata_returns_empty_on_error(self):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = BotoCoreError()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("documents.services.boto3", mock_boto3):
            service = DocumentService()
            metadata = service.get_document_metadata("cases/C1/documents/missing.pdf")

        self.assertEqual(metadata, {})
