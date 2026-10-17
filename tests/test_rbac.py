from dotenv import load_dotenv
load_dotenv()

import pytest
from app.rag.retriever import retrieve_documents, ROLE_CLEARANCE


def test_employee_cannot_retrieve_finance_only():
    docs = retrieve_documents("Q3 revenue", "employee", ["sales"])
    assert not any(doc.metadata.get("access_level") == "finance_only" for doc in docs)


def test_employee_cannot_retrieve_hr_only():
    docs = retrieve_documents("compensation bands", "employee", ["sales"])
    assert not any(doc.metadata.get("access_level") == "hr_only" for doc in docs)


def test_finance_can_retrieve_finance_only():
    docs = retrieve_documents("Q3 revenue", "finance", ["finance"])
    assert any(doc.metadata.get("access_level") == "finance_only" for doc in docs)
    assert any(doc.metadata.get("doc_id") == "FIN-BUDGET-001" for doc in docs)


def test_hr_can_retrieve_hr_only():
    docs = retrieve_documents("compensation bands", "hr", ["hr"])
    assert any(doc.metadata.get("access_level") == "hr_only" for doc in docs)


def test_employee_can_retrieve_internal():
    docs = retrieve_documents("leave policy", "employee", ["sales"])
    assert any(doc.metadata.get("access_level") == "internal" for doc in docs)
    assert any(doc.metadata.get("doc_id") in ("PUB-LEAVE-001", "PUB-HANDBOOK-001") for doc in docs)


def test_unknown_role_defaults_to_public_only():
    docs = retrieve_documents("leave policy", "guest", ["sales"])
    assert not any(
        doc.metadata.get("access_level") in ("internal", "confidential", "hr_only", "finance_only", "it_only")
        for doc in docs
    )

