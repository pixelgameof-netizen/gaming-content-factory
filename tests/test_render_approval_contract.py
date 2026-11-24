import pathlib
import re
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


class RenderApprovalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.decide = function_body(cls.sql, "gcf_decide_render_output")
        cls.pending = function_body(cls.sql, "gcf_list_pending_approvals")

    def test_decision_requires_authenticated_owner(self):
        self.assertIn("v_owner uuid := auth.uid()", self.decide)
        self.assertIn("a.owner_id = v_owner", self.decide)
        self.assertIn("o.owner_id = v_owner", self.decide)
        self.assertIn("authentication required", self.decide)

    def test_decision_is_bound_to_exact_output_version_hash_and_platform(self):
        for required in (
            "v_approval.video_output_id <> p_video_output_id",
            "v_approval.output_version <> v_output.version_no",
            "lower(v_approval.output_sha256) <> lower(p_sha256)",
            "lower(coalesce(v_output.sha256,'')) <> lower(p_sha256)",
            "v_output.platform is distinct from p_platform",
            "v_output.quality_status is distinct from 'passed'",
            "v_output.storage_bucket is distinct from 'gcf-video-outputs'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.decide)

    def test_only_pending_decisions_can_change_and_conflicts_are_rejected(self):
        self.assertIn("v_approval.status <> 'pending'", self.decide)
        self.assertIn("v_approval.status = p_decision", self.decide)
        self.assertIn("approval has already been decided", self.decide)
        self.assertIn("decided_by = v_owner", self.decide)
        self.assertIn("decided_at = now()", self.decide)

    def test_pending_list_is_owner_scoped_and_hides_decided_rows(self):
        self.assertIn("a.owner_id = auth.uid()", self.pending)
        self.assertIn("o.owner_id = auth.uid()", self.pending)
        self.assertIn("a.status = 'pending'", self.pending)

    def test_approval_rpcs_are_not_granted_to_public_or_anon(self):
        self.assertIn(
            "revoke all on function public.gcf_decide_render_output(uuid, uuid, text, text, text, text) from public, anon, service_role;",
            self.sql,
        )
        self.assertIn(
            "grant execute on function public.gcf_decide_render_output(uuid, uuid, text, text, text, text) to authenticated;",
            self.sql,
        )


if __name__ == "__main__":
    unittest.main()
