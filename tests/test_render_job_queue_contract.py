import pathlib
import unittest


MIGRATION = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "202611220001_render_jobs.sql"


def function_body(sql: str, name: str) -> str:
    marker = f"create or replace function public.{name}"
    start = sql.lower().find(marker.lower())
    if start < 0:
        raise AssertionError(f"Missing function definition: {name}")
    end = sql.find("$$;", start)
    if end < 0:
        raise AssertionError(f"Unterminated function definition: {name}")
    return sql[start:end + 3]


class RenderQueueContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.claim_next = function_body(cls.sql, "gcf_claim_next_render_job")
        cls.claim_one = function_body(cls.sql, "gcf_claim_render_job")
        cls.create_job = function_body(cls.sql, "gcf_create_render_job")
        cls.prepare_upload = function_body(cls.sql, "gcf_prepare_render_job_upload")

    def test_queue_claim_is_atomic_and_skips_locked_rows(self):
        self.assertIn("for update skip locked", self.claim_next.lower())
        self.assertIn("limit 1", self.claim_next.lower())
        self.assertIn("status = 'preparing'", self.claim_next)
        self.assertIn("attempt_count = attempt_count + 1", self.claim_next)

    def test_stale_preparing_jobs_are_reclaimable_but_attempts_are_bounded(self):
        for body in (self.claim_next, self.claim_one):
            self.assertIn("interval '30 minutes'", body)
            self.assertIn("attempt_count < 3", body)
            self.assertIn("expires_at is null", body)
            self.assertIn("expires_at > now()", body)

    def test_uploading_jobs_are_not_silently_reclaimed(self):
        self.assertNotIn("status = 'uploading'", self.claim_next)
        self.assertNotIn("status = 'uploading'", self.claim_one)
        self.assertIn("j.status in ('queued', 'preparing', 'uploading')", self.prepare_upload)

    def test_job_creation_is_authenticated_and_owner_scoped(self):
        self.assertIn("v_owner uuid := auth.uid()", self.create_job)
        self.assertIn("authentication required", self.create_job)
        self.assertIn("p.owner_id = v_owner", self.create_job)
        self.assertIn("a.owner_id = v_owner", self.create_job)
        self.assertIn("a.package_id = p_package_id", self.create_job)
        self.assertIn("a.rights_status = 'approved'", self.create_job)
        self.assertIn("v_review.status is distinct from 'approved_by_owner'", self.create_job)

    def test_manifest_is_bounded_and_file_names_are_constrained(self):
        self.assertIn("v_asset_count < 1 or v_asset_count > 20", self.create_job)
        self.assertIn("v_asset_count <> v_unique_ids", self.create_job)
        self.assertIn("v_asset_count <> v_unique_names", self.create_job)
        self.assertIn("^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$", self.create_job)
        self.assertIn("v_asset.sha256 !~* '^[a-f0-9]{64}$'", self.create_job)


if __name__ == "__main__":
    unittest.main()
