from src.main import app
from src.request.write_summary_request import WriteSummaryRequest


def test_requested_api_routes_are_registered():
    routes = {
        (route.path, frozenset(route.methods or set()))
        for route in app.routes
        if hasattr(route, "methods")
    }

    assert ("/books/upload", frozenset({"POST"})) in routes
    assert ("/books", frozenset({"GET"})) in routes
    assert ("/books/{book_id}", frozenset({"GET"})) in routes
    assert ("/sections/{section_id}", frozenset({"GET"})) in routes
    assert ("/sections/{section_id}/facts", frozenset({"GET"})) in routes
    assert ("/sections/{section_id}/facts/extraction", frozenset({"POST"})) in routes
    assert ("/sections/{section_id}/summaries", frozenset({"POST"})) in routes
    assert ("/audit_reports/{audit_report_id}", frozenset({"GET"})) in routes
    assert ("/sections/{section_id}/audit_reports", frozenset({"GET"})) in routes
    assert ("/facts/extraction/{job_id}", frozenset({"GET"})) in routes
    assert ("/jobs", frozenset({"GET"})) in routes
    assert ("/jobs/{job_id}", frozenset({"GET"})) in routes


def test_summary_request_accepts_summary_text_only():
    request = WriteSummaryRequest(summary_text="This is my section summary.")

    assert request.section_id is None
    assert request.summary_text == "This is my section summary."
