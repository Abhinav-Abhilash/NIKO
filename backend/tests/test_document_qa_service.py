from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.services.document_service import (
    DocumentService,
    chunk_text,
)
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.document_search_skill import DocumentSearchSkill


@pytest.fixture
def sample_files(tmp_path: Path) -> dict[str, Path]:
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    # Markdown document
    arch_doc = doc_dir / "architecture.md"
    arch_doc.write_text(
        "# NIKO System Architecture\n\n"
        "NIKO is a private desktop assistant built on FastAPI, SQLite FTS5, and Tauri v2.\n"
        "It supports multi-provider LLM orchestration with Gemini, Groq, and OpenRouter.\n"
        "Security is enforced with human-in-the-loop approval gates and cryptographic tokens.\n",
        encoding="utf-8",
    )

    # Code document
    code_doc = doc_dir / "service_worker.py"
    code_doc.write_text(
        "class Worker:\n"
        "    def run(self):\n"
        "        # Perform background telemetry aggregation and maintenance\n"
        "        print('Worker running telemetry loop')\n",
        encoding="utf-8",
    )

    return {"arch": arch_doc, "code": code_doc}


@pytest.fixture
async def owner_user_and_headers(db_session: AsyncSession) -> tuple[User, dict[str, str]]:
    from datetime import timedelta

    from backend.app.config import get_settings
    from backend.app.core.security import create_jwt_token, hash_password

    owner = User(
        username="owner_doc_test",
        password_hash=hash_password("SuperSecret123!"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    settings = get_settings()
    token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://127.0.0.1:5173",
        "X-CSRF-Token": "test-csrf",
    }
    return owner, headers


def test_chunk_text_utility() -> None:
    text = "Word " * 500  # ~2500 characters
    chunks = chunk_text(text, chunk_size=1000, overlap=100)
    assert len(chunks) >= 3
    assert all(len(c) <= 1000 for c in chunks)


@pytest.mark.asyncio
async def test_document_ingestion_and_fts5_search(
    db_session: AsyncSession,
    owner_user_and_headers: tuple[User, dict[str, str]],
    sample_files: dict[str, Path],
) -> None:
    owner, _headers = owner_user_and_headers
    service = DocumentService(db_session)

    # 1. Ingest markdown document
    doc = await service.ingest_file(
        user_id=owner.id,
        file_path_str=str(sample_files["arch"]),
        title="Architecture Specification",
    )
    assert doc.title == "Architecture Specification"
    assert doc.chunk_count >= 1

    # 2. Search query matches
    results = await service.search(user_id=owner.id, query="Tauri FastAPI orchestration", top_k=3)
    assert len(results) >= 1
    assert "Architecture Specification" in results[0]["document_title"]
    assert "multi-provider" in results[0]["content"]

    # 3. List documents
    docs = await service.list_documents(user_id=owner.id)
    assert len(docs) == 1
    assert docs[0].id == doc.id

    # 4. Delete document
    deleted = await service.delete_document(user_id=owner.id, document_id=doc.id)
    assert deleted is True
    assert len(await service.list_documents(user_id=owner.id)) == 0


@pytest.mark.asyncio
async def test_document_search_skill_execution(
    db_session: AsyncSession,
    owner_user_and_headers: tuple[User, dict[str, str]],
    sample_files: dict[str, Path],
) -> None:
    owner, _headers = owner_user_and_headers
    skill = DocumentSearchSkill()
    assert skill.manifest.name == "document_search"
    assert skill.manifest.default_tier == "SAFE"

    ctx = SkillContext(request_id="req_doc_1", user_id=owner.id, provenance="direct")

    # Ingest via skill
    res_ingest = await skill.execute(
        {"action": "ingest", "file_path": str(sample_files["code"])},
        ctx,
    )
    assert res_ingest.success is True
    assert res_ingest.data["status"] == "ingested"

    # Search via skill
    res_search = await skill.execute(
        {"action": "search", "query": "telemetry loop worker"},
        ctx,
    )
    assert res_search.success is True
    assert res_search.data["results_count"] >= 1
    assert "Worker running" in res_search.data["chunks"][0]["content"]


@pytest.mark.asyncio
async def test_document_rest_api(
    async_client: AsyncClient,
    owner_user_and_headers: tuple[User, dict[str, str]],
    sample_files: dict[str, Path],
) -> None:
    owner, headers = owner_user_and_headers

    # 1. Ingest file via API
    payload = {"file_path": str(sample_files["arch"]), "title": "API Ingested Doc"}
    res_ingest = await async_client.post("/api/v1/documents/ingest", json=payload, headers=headers)
    assert res_ingest.status_code == 200
    doc_data = res_ingest.json()["document"]
    doc_id = doc_data["id"]

    # 2. List documents via API
    res_list = await async_client.get("/api/v1/documents", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Search documents via API
    res_search = await async_client.get("/api/v1/documents/search?query=FastAPI", headers=headers)
    assert res_search.status_code == 200
    assert res_search.json()["results_count"] >= 1

    # 4. Delete document via API
    res_del = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True
