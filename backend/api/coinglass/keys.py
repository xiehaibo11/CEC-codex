from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config.settings import COINGLASS_API_KEY
from database.models import CoinGlassUserKey, User
from utils.encryption import decrypt_private_key, encrypt_private_key

logger = logging.getLogger(__name__)


def _server_coinglass_key() -> str:
    return (COINGLASS_API_KEY or os.getenv("COINGLASS_API_KEY", "")).strip()


def _mask_key(api_key: str) -> str:
    if len(api_key) <= 10:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


def _user_key_record(db: Session, user_id: int) -> CoinGlassUserKey | None:
    return db.query(CoinGlassUserKey).filter(CoinGlassUserKey.user_id == user_id).first()


def _decrypt_user_key(record: CoinGlassUserKey) -> str:
    try:
        return decrypt_private_key(record.api_key_encrypted)
    except Exception as exc:
        logger.warning("Failed to decrypt CoinGlass key for user_id=%s", record.user_id)
        raise HTTPException(status_code=500, detail="Stored CoinGlass API key cannot be decrypted") from exc


def _effective_key(db: Session, user: User) -> tuple[str, str, str | None]:
    record = _user_key_record(db, user.id)
    if record:
        api_key = _decrypt_user_key(record)
        return api_key, "user", record.key_masked

    server_key = _server_coinglass_key()
    if server_key:
        return server_key, "server", _mask_key(server_key)

    return "", "none", None


def _upsert_user_key(db: Session, user_id: int, api_key: str, subscription_data: dict) -> CoinGlassUserKey:
    record = _user_key_record(db, user_id)
    if record:
        record.api_key_encrypted = encrypt_private_key(api_key)
        record.key_masked = _mask_key(api_key)
        record.plan_level = subscription_data.get("level")
        record.expire_time = subscription_data.get("expire_time")
        record.expired = subscription_data.get("expired")
        record.last_validated_at = datetime.utcnow()
        return record

    record = CoinGlassUserKey(
        user_id=user_id,
        api_key_encrypted=encrypt_private_key(api_key),
        key_masked=_mask_key(api_key),
        plan_level=subscription_data.get("level"),
        expire_time=subscription_data.get("expire_time"),
        expired=subscription_data.get("expired"),
        last_validated_at=datetime.utcnow(),
    )
    db.add(record)
    return record
