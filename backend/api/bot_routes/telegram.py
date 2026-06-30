"""Telegram-specific bot endpoints and message processing."""
import asyncio
import json

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from services.bot_service import (
    save_bot_config,
    get_decrypted_bot_token,
    update_bot_status,
)
from services.telegram_bot_service import (
    validate_telegram_token,
    setup_telegram_webhook,
    remove_telegram_webhook,
    send_telegram_message,
)

from ._router import router
from .tool_labels import _get_ui_language, _get_tool_label


class TelegramConnectRequest(BaseModel):
    bot_token: str


@router.post("/telegram/connect")
async def connect_telegram_bot(
    request: TelegramConnectRequest,
    db: Session = Depends(get_db)
):
    """Validate token, save config, and start Long Polling for Telegram bot."""
    # Validate new token first
    result = await validate_telegram_token(request.bot_token)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail=f"Invalid bot token: {result.get('error')}")

    # If rebinding: stop old polling and remove webhook
    old_token = get_decrypted_bot_token(db, "telegram")
    if old_token and old_token != request.bot_token:
        try:
            from services.telegram_bot_service import stop_telegram_polling
            await stop_telegram_polling()
            await remove_telegram_webhook(old_token)
        except Exception:
            pass  # Old token may be invalid, that's fine

    # Save config (creates or updates)
    save_bot_config(
        db=db,
        platform="telegram",
        bot_token=request.bot_token,
        bot_username=result.get("username"),
        bot_app_id=result.get("bot_id"),
    )

    # Start Long Polling mode (no HTTPS/public URL required)
    from services.telegram_bot_service import start_telegram_polling
    polling_result = await start_telegram_polling(request.bot_token)
    if not polling_result["success"]:
        update_bot_status(db, "telegram", "error", polling_result.get("error"))
        raise HTTPException(status_code=500, detail=f"Failed to start polling: {polling_result.get('error')}")

    update_bot_status(db, "telegram", "connected")

    # Register Telegram adapter
    from services.telegram_bot_service import get_telegram_adapter
    from services.bot_adapter import register_adapter
    adapter = get_telegram_adapter()
    await adapter.start(request.bot_token)
    register_adapter(adapter)

    # Create or get the shared Bot conversation (one per user, shared across platforms)
    from database.models import HyperAiConversation
    bot_conv = db.query(HyperAiConversation).filter(
        HyperAiConversation.is_bot_conversation == True
    ).first()
    if not bot_conv:
        bot_conv = HyperAiConversation(
            title="Hyper AI Bot",
            is_bot_conversation=True
        )
        db.add(bot_conv)
        db.commit()
        db.refresh(bot_conv)

    return {
        "success": True,
        "bot_username": result.get("username"),
        "mode": "polling",
        "conversation_id": bot_conv.id,
    }


@router.post("/telegram/disconnect")
async def disconnect_telegram_bot(db: Session = Depends(get_db)):
    """Stop polling and disconnect Telegram bot."""
    token = get_decrypted_bot_token(db, "telegram")
    if not token:
        raise HTTPException(status_code=404, detail="Telegram bot not configured")

    # Stop polling and remove webhook
    from services.telegram_bot_service import stop_telegram_polling
    await stop_telegram_polling()
    await remove_telegram_webhook(token)

    update_bot_status(db, "telegram", "disconnected")
    return {"success": True}


@router.post("/telegram/retry-webhook")
async def retry_telegram_connection(
    db: Session = Depends(get_db)
):
    """Retry connection for an already-configured Telegram bot."""
    token = get_decrypted_bot_token(db, "telegram")
    if not token:
        raise HTTPException(status_code=404, detail="Telegram bot not configured")

    # Start polling mode
    from services.telegram_bot_service import start_telegram_polling
    polling_result = await start_telegram_polling(token)
    if not polling_result["success"]:
        update_bot_status(db, "telegram", "error", polling_result.get("error"))
        raise HTTPException(status_code=500, detail=f"Failed to start polling: {polling_result.get('error')}")

    update_bot_status(db, "telegram", "connected")
    return {"success": True}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive incoming updates from Telegram.
    This is called by Telegram servers when a user sends a message to the bot.
    """
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}  # Return ok to avoid Telegram retries

    # Extract message if present
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user = message.get("from", {})

    if not chat_id or not text:
        return {"ok": True}

    # Get bot token
    token = get_decrypted_bot_token(db, "telegram")
    if not token:
        return {"ok": True}

    # Process message with Hyper AI (async, non-blocking)
    asyncio.create_task(
        _process_telegram_message(token, chat_id, text, user, db)
    )
    print(f"[TG-WEBHOOK] Dispatched task for chat_id={chat_id} text={text[:50]}", flush=True)

    return {"ok": True}


async def _process_telegram_message(
    token: str,
    chat_id: int,
    text: str,
    user: dict,
    db: Session
):
    """
    Process a Telegram message through Hyper AI and send response.
    Runs as a background task to avoid blocking the webhook response.
    Reply unicast: response only goes to the originating chat_id.
    """
    from services.hyper_ai_service import (
        get_or_create_conversation,
        stream_chat_response,
    )
    from database.models import HyperAiConversation, BotChatBinding
    from database.connection import SessionLocal
    from sqlalchemy import func

    # Use a new db session for async context
    db_session = SessionLocal()
    try:
        # Record chat binding for push broadcast
        binding = db_session.query(BotChatBinding).filter(
            BotChatBinding.platform == "telegram",
            BotChatBinding.chat_id == str(chat_id)
        ).first()
        if not binding:
            binding = BotChatBinding(
                platform="telegram",
                chat_id=str(chat_id),
                username=user.get("username"),
                display_name=user.get("first_name", "") + " " + user.get("last_name", "")
            )
            db_session.add(binding)
        else:
            binding.last_message_at = func.current_timestamp()
            binding.is_active = True
        db_session.commit()

        # Find the shared Bot conversation (shared across all platforms)
        conv = db_session.query(HyperAiConversation).filter(
            HyperAiConversation.is_bot_conversation == True
        ).first()

        if not conv:
            # Fallback: create one if not exists (shouldn't happen normally)
            conv = HyperAiConversation(
                title="Hyper AI Bot",
                is_bot_conversation=True
            )
            db_session.add(conv)
            db_session.commit()
            db_session.refresh(conv)

        print(f"[TG-PROCESS] Using conv id={conv.id}, processing text: {text[:50]}", flush=True)

        # Determine UI language for tool progress messages
        lang = _get_ui_language(db_session)

        # Run synchronous AI processing in a thread to avoid blocking event loop
        def process_ai_sync():
            """Synchronous AI processing - runs in thread pool."""
            events = []
            for event in stream_chat_response(db_session, conv.id, text):
                events.append(event)
            return events

        import asyncio
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, process_ai_sync)

        # Process events and collect response
        full_response = ""
        tool_calls = []
        for event in events:
            event_type = None
            data_str = None
            for line in event.split("\n"):
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:]

            if not data_str:
                continue
            try:
                data = json.loads(data_str)
                if event_type == "tool_call" and data.get("name"):
                    tool_calls.append(data["name"])
                elif event_type == "content":
                    full_response += data.get("text", "")
                elif event_type == "error":
                    full_response = f"Error: {data.get('message', 'Unknown error')}"
            except json.JSONDecodeError:
                pass

        # Send tool call progress (combined into one message)
        if tool_calls:
            labels = [_get_tool_label(name, lang) for name in tool_calls[:5]]
            if len(tool_calls) > 5:
                labels.append(f"...+{len(tool_calls) - 5} more")
            progress_msg = "【🤖Hyper AI】" + " → ".join(labels)
            await send_telegram_message(token, chat_id, progress_msg)

        print(f"[TG-PROCESS] AI response length={len(full_response)}", flush=True)

        # Send response back to Telegram
        if full_response:
            result = await send_telegram_message(token, chat_id, full_response)
            print(f"[TG-PROCESS] Send result={result}", flush=True)

    except Exception as e:
        import logging
        print(f"[TG-PROCESS] ERROR: {type(e).__name__}: {e}", flush=True)
        logging.getLogger(__name__).error(f"Telegram message processing failed: {e}")
        # Try to send error message
        try:
            await send_telegram_message(token, chat_id, "Sorry, an error occurred while processing your message.")
        except Exception:
            pass
    finally:
        db_session.close()
