from dotenv import load_dotenv
load_dotenv()

from app.guardrails.groundedness.pipeline import verify_groundedness
from app.guardrails.groundedness.citation_check import (
    extract_citations, verify_citations,
)
from app.guardrails.groundedness.claim_splitter import split_into_claims
from app.guardrails.groundedness.anchor_check import (
    extract_anchors, verify_anchors,
)


def test_extract_citations_bracketed_and_bare():
    text = "Employees get 12 days [HR-LEAVE-001]. See IT-SEC-001 for details."
    ids = extract_citations(text)
    assert "HR-LEAVE-001" in ids
    assert "IT-SEC-001" in ids
    assert len(ids) == 2  # deduplicated


def test_fabricated_citation_detected():
    result = verify_citations(
        "See [HR-FAKE-999].",
        {"HR-LEAVE-001", "IT-SEC-001"},
    )
    assert result["valid"] is False
    assert "HR-FAKE-999" in result["fabricated_ids"]
    assert result["reason"] == "fabricated_citation"


def test_no_citation_flagged_when_factual():
    long_answer = (
        "Employees are entitled to twelve days of casual leave and "
        "eighteen days of earned leave per calendar year, with carry-forward "
        "provisions subject to annual caps of 30 days."
    )
    result = verify_citations(long_answer, {"HR-LEAVE-001"})
    assert result["valid"] is False
    assert result["reason"] == "missing_citations"


def test_claim_splitter_filters_greetings():
    text = "Hello. Employees get 12 days of leave. Thanks for asking."
    claims = split_into_claims(text)
    # Only the substantive middle claim survives
    assert len(claims) == 1
    assert "12 days" in claims[0]


def test_anchor_extraction_finds_numbers():
    text = "Employees get INR 5,000 per quarter and 26 weeks of leave."
    anchors = extract_anchors(text)
    assert "monetary" in anchors
    assert "duration" in anchors


def test_unsupported_anchor_detected():
    anchors = {"duration": ["99 days"]}
    result = verify_anchors(anchors, "Employees get 12 days of leave.")
    assert result["valid"] is False
    assert "99 days" in result["unverified"]


def test_pipeline_passes_clean_answer():
    result = verify_groundedness(
        "Employees get 12 days [HR-LEAVE-001].",
        [{"doc_id": "HR-LEAVE-001",
          "content": "Employees get 12 days of casual leave per year."}],
    )
    assert result["grounded"] is True
    assert result["stage"] == "passed"


def test_pipeline_catches_fabricated_citation():
    result = verify_groundedness(
        "Employees get 12 days [HR-FAKE-999].",
        [{"doc_id": "HR-LEAVE-001",
          "content": "Employees get 12 days of leave."}],
    )
    assert result["grounded"] is False
    assert result["stage"] == "citations"


def test_pipeline_catches_unsupported_anchor():
    result = verify_groundedness(
        "Employees get 99 days of leave [HR-LEAVE-001].",
        [{"doc_id": "HR-LEAVE-001",
          "content": "Employees get 12 days of leave."}],
    )
    assert result["grounded"] is False
    assert result["stage"] == "anchors"


def test_pipeline_rejects_empty_context():
    result = verify_groundedness(
        "Employees get 12 days of leave.",
        [],
    )
    assert result["grounded"] is False
    assert result["stage"] == "no_context"

