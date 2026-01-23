import sys
import types
import unittest

stub_db = types.ModuleType("backend.app.core.db")


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _dummy_session_local():
    return _DummySession()


stub_db.TargetSessionLocal = _dummy_session_local
sys.modules["backend.app.core.db"] = stub_db

from backend.app.services import faq_extraction


class AutoReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = faq_extraction.FAQExtractionService(max_workers=1)
        self.service.auto_review_max_retries = 0
        self.service.auto_review_retry_delay_seconds = 0
        faq_extraction.settings.aico.auto_review_url = "http://dummy"
        faq_extraction.settings.aico.compare_review_url = "http://compare"
        faq_extraction.settings.aico.chatbot_api_key = "dummy"

    def test_auto_review_approved(self) -> None:
        self.service._call_aico = lambda query, url=None: "approved"
        self.assertEqual(self.service._run_auto_review("q", "a"), "approved")
        self.assertEqual(self.service._determine_pending_status("q", "a", "call"), "pending")

    def test_auto_review_rejected(self) -> None:
        self.service._call_aico = lambda query, url=None: "rejected"
        self.assertEqual(self.service._run_auto_review("q", "a"), "rejected")
        self.assertEqual(self.service._determine_pending_status("q", "a", "call"), "auto_rejected")

    def test_auto_review_json_approved(self) -> None:
        self.service._call_aico = lambda query, url=None: '{"result":"approved"}'
        self.assertEqual(self.service._run_auto_review("q", "a"), "approved")

    def test_auto_review_unexpected_text(self) -> None:
        self.service._call_aico = lambda query, url=None: "maybe"
        self.assertEqual(self.service._run_auto_review("q", "a"), "rejected")

    def test_auto_review_failure_fallback(self) -> None:
        def raise_error(*_args, **_kwargs):
            raise RuntimeError("boom")

        self.service._call_aico = raise_error
        status = self.service._determine_pending_status("q", "a", "call")
        self.assertEqual(status, "pending")

    def test_compare_review_rejected(self) -> None:
        faq_extraction.settings.aico.auto_review_url = "http://auto"
        faq_extraction.settings.aico.compare_review_url = "http://compare"

        def stub(query, url=None):
            if url == "http://compare":
                return "rejected"
            return "approved"

        self.service._call_aico = stub
        status = self.service._determine_pending_status("q", "a", "call")
        self.assertEqual(status, "auto_rejected")

    def test_compare_review_failure_fallback(self) -> None:
        faq_extraction.settings.aico.auto_review_url = "http://auto"
        faq_extraction.settings.aico.compare_review_url = "http://compare"

        def stub(query, url=None):
            if url == "http://compare":
                raise RuntimeError("boom")
            return "approved"

        self.service._call_aico = stub
        status = self.service._determine_pending_status("q", "a", "call")
        self.assertEqual(status, "pending")
