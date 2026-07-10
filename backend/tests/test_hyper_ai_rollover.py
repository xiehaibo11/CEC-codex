"""Conversation generation rollover: archive -> compress -> fresh round.

In-conversation compression (summaries + compression points) can dodge the
context limit forever, but each generation of stacked summaries degrades the
context - the classic long-running drift the user observes as hallucination.
Policy: after the raw conversation outgrows the model window budget or too
many compression generations pile up, SAVE the trading text to an archive
FIRST, extract memories + a final summary, then hard-reset into a brand-new
conversation seeded with that summary.

Limits are model-aware (DeepSeek V4: 1M context, 384K max output).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import HyperAiConversation, HyperAiMessage
from services.hyper_ai_service import rollover as ro


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[HyperAiConversation.__table__, HyperAiMessage.__table__]
    )
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _make_conversation(db, n_messages=4, content="hello", compression_points=None):
    conv = HyperAiConversation(title="trading chat")
    if compression_points is not None:
        conv.compression_points = json.dumps(compression_points)
    db.add(conv)
    db.commit()
    for i in range(n_messages):
        db.add(
            HyperAiMessage(
                conversation_id=conv.id,
                role="user" if i % 2 == 0 else "assistant",
                content=content,
            )
        )
    db.commit()
    db.refresh(conv)
    return conv


class TestShouldRollover:
    def test_small_fresh_conversation_does_not_rollover(self, session):
        conv = _make_conversation(session)
        assert ro.should_rollover(session, conv, "deepseek-v4") is None

    def test_rollover_when_compression_generations_exhausted(self, session):
        points = [
            {"message_id": i, "summary": "s", "compressed_at": "t"}
            for i in range(ro.MAX_COMPRESSION_GENERATIONS)
        ]
        conv = _make_conversation(session, compression_points=points)
        reason = ro.should_rollover(session, conv, "deepseek-v4")
        assert reason is not None and "压缩" in reason

    def test_rollover_when_raw_tokens_exceed_window_budget(self, session, monkeypatch):
        conv = _make_conversation(session, n_messages=2)
        monkeypatch.setattr(ro, "_conversation_raw_tokens", lambda *a, **k: 900_000)
        reason = ro.should_rollover(session, conv, "deepseek-v4")
        assert reason is not None and "token" in reason.lower()

    def test_rollover_when_output_headroom_gone(self, session, monkeypatch):
        # 1M window, current 960K: even a modest response budget no longer fits.
        conv = _make_conversation(session, n_messages=2)
        monkeypatch.setattr(ro, "_conversation_raw_tokens", lambda *a, **k: 960_000)
        assert ro.should_rollover(session, conv, "deepseek-v4") is not None


class TestRolloverExecution:
    @pytest.fixture()
    def patched(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HYPER_AI_ARCHIVE_DIR", str(tmp_path))
        monkeypatch.setattr(
            "services.ai_context_compression_service.generate_summary",
            lambda messages, api_config: "compressed trading summary",
        )
        extracted = []
        monkeypatch.setattr(
            ro, "_extract_memories_async", lambda *a, **k: extracted.append(True)
        )
        return {"tmp_path": tmp_path, "extracted": extracted}

    def test_archives_trading_text_before_new_round(self, session, patched):
        conv = _make_conversation(session, n_messages=4, content="buy BTC at 63000")

        new_conv = ro.rollover_conversation(session, conv, {"model": "deepseek-v4"})

        archives = list(patched["tmp_path"].glob("conversation_*.json"))
        assert len(archives) == 1
        payload = json.loads(archives[0].read_text())
        assert payload["conversation_id"] == conv.id
        assert len(payload["messages"]) == 4
        assert "buy BTC at 63000" in json.dumps(payload)
        assert new_conv.id != conv.id

    def test_new_round_seeded_with_summary(self, session, patched):
        conv = _make_conversation(session)

        new_conv = ro.rollover_conversation(session, conv, {"model": "deepseek-v4"})

        points = json.loads(new_conv.compression_points)
        assert points[-1]["summary"] == "compressed trading summary"
        # message_id 0 -> no new messages are filtered out by the seed point
        assert points[-1]["message_id"] == 0

    def test_old_conversation_marked_rolled_over(self, session, patched):
        conv = _make_conversation(session)

        new_conv = ro.rollover_conversation(session, conv, {"model": "deepseek-v4"})

        session.refresh(conv)
        assert f"#{new_conv.id}" in conv.title
        assert "已归档" in conv.title

    def test_memory_extraction_invoked(self, session, patched):
        conv = _make_conversation(session)
        ro.rollover_conversation(session, conv, {"model": "deepseek-v4"})
        assert patched["extracted"]
