import contextlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "render" / "upload_supabase_tus.py"
SPEC = importlib.util.spec_from_file_location("upload_supabase_tus", MODULE_PATH)
UPLOADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPLOADER)

OWNER = "11111111-1111-4111-8111-111111111111"
PACKAGE = "22222222-2222-4222-8222-222222222222"
JOB = "33333333-3333-4333-8333-333333333333"
FILE_ID = "44444444-4444-4444-8444-444444444444"
PROJECT_REF = "pyrrcfegucvxyxlxzowu"
TOKEN = "signed-upload-token-not-for-logs"


class FakeResponse:
    def __init__(self, status, headers):
        self.status = status
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ResumableUploadTests(unittest.TestCase):
    def test_uploads_in_chunks_with_signed_token_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = pathlib.Path(temp_dir) / "output.mp4"
            payload = b"gcf-test" * ((6 * 1024 * 1024 + 17) // 8 + 1)
            payload = payload[: 6 * 1024 * 1024 + 17]
            source.write_bytes(payload)
            uploaded = bytearray()
            patch_calls = []
            expected_path = f"{OWNER}/{PACKAGE}/render-jobs/{JOB}/{FILE_ID}.mp4"

            def fake_request(url, method, headers, data=None):
                if method == "POST":
                    self.assertTrue(url.endswith("/storage/v1/upload/resumable/sign"))
                    self.assertEqual(headers["x-signature"], TOKEN)
                    self.assertEqual(headers["Upload-Length"], str(len(payload)))
                    self.assertIn("bucketName ", headers["Upload-Metadata"])
                    self.assertIn("objectName ", headers["Upload-Metadata"])
                    return FakeResponse(201, {
                        "Location": f"https://{PROJECT_REF}.storage.supabase.co/storage/v1/upload/resumable/test"
                    })
                if method == "PATCH":
                    self.assertEqual(headers["x-signature"], TOKEN)
                    self.assertEqual(headers["Upload-Offset"], str(len(uploaded)))
                    self.assertEqual(headers["Content-Type"], "application/offset+octet-stream")
                    uploaded.extend(data)
                    patch_calls.append(len(data))
                    return FakeResponse(204, {"Upload-Offset": str(len(uploaded))})
                raise AssertionError(f"Unexpected HTTP method: {method}")

            argv = [
                "upload_supabase_tus.py", "--file", str(source), "--path", expected_path,
                "--project-ref", PROJECT_REF,
            ]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), patch.dict(os.environ, {"SUPABASE_UPLOAD_TOKEN": TOKEN}), \
                 patch.object(UPLOADER, "request", side_effect=fake_request), contextlib.redirect_stdout(output):
                UPLOADER.main()

            self.assertEqual(bytes(uploaded), payload)
            self.assertEqual(len(patch_calls), 2)
            self.assertIn("resumable TUS", output.getvalue())
            self.assertNotIn(TOKEN, output.getvalue())

    def test_rejects_path_outside_owner_package_job_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = pathlib.Path(temp_dir) / "output.mp4"
            source.write_bytes(b"x" * 2048)
            argv = ["upload_supabase_tus.py", "--file", str(source), "--path", "../other.mp4", "--project-ref", PROJECT_REF]
            with patch.object(sys, "argv", argv), patch.dict(os.environ, {"SUPABASE_UPLOAD_TOKEN": TOKEN}), \
                 patch.object(UPLOADER, "request") as mocked:
                with self.assertRaises(SystemExit):
                    UPLOADER.main()
                mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
