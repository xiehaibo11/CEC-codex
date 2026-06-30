"""Discord-specific bot endpoints and message processing."""
import asyncio
import json

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from services.bot_service import (
    get_bot_config,
    save_bot_config,
    get_decrypted_bot_token,
    update_bot_status,
)
from services.discord_bot_service import (
    validate_discord_token,
    start_discord_gateway,
    stop_discord_gateway,
    send_discord_message_via_client,
    is_discord_client_running,
)

from ._router import router
from .tool_labels import _get_ui_language, _get_tool_label


class DiscordConnectRequest(BaseModel):
    bot_token: str


@router.post("/discord/connect")
async def connect_discord_bot(
    request: DiscordConnectRequest,
    db: Session = Depends(get_db)
):
    """
    Validate token, save config, and start Gateway client for Discord bot.
    Unlike Telegram (webhook-based), Discord uses persistent Gateway connection.
    """
    # Validate token first
    result = await validate_discord_token(request.bot_token)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail=f"Invalid bot token: {result.get('error')}")

    # Save config (creates or updates)
    save_bot_config(
        db=db,
        platform="discord",
        bot_token=request.bot_token,
        bot_username=result.get("username"),
        bot_app_id=result.get("bot_id"),
    )

    update_bot_status(db, "discord", "connected")

    # Register Discord adapter
    from services.discord_bot_service import get_discord_adapter
    from services.bot_adapter import register_adapter
    adapter = get_discord_adapter()
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

    # Start Gateway client in background
    asyncio.create_task(_start_discord_gateway_background(request.bot_token))

    return {
        "success": True,
        "bot_username": result.get("username"),
        "conversation_id": bot_conv.id,
    }


async def _start_discord_gateway_background(token: str):
    """Start Discord Gateway in background with message handler."""
    async def handle_discord_message(user_id: int, username: str, display_name: str, text: str) -> str:
        """Process Discord DM through Hyper AI."""
        return await _process_discord_message_internal(user_id, username, display_name, text)

    try:
        await start_discord_gateway(token, handle_discord_message)
    except Exception as e:
        print(f"[Discord] Gateway startup failed: {e}", flush=True)


async def _process_discord_message_internal(
    user_id: int,
    username: str,
    display_name: str,
    text: str
) -> str:
    """
    Process a Discord DM through Hyper AI and return response.
    Similar to _process_telegram_message but returns string instead of sending directly.
    """
    from services.hyper_ai_service import stream_chat_response
    from database.models import HyperAiConversation, BotChatBinding
    from database.connection import SessionLocal
    from sqlalchemy import func

    db_session = SessionLocal()
    try:
        # Record chat binding for push broadcast
        binding = db_session.query(BotChatBinding).filter(
            BotChatBinding.platform == "discord",
            BotChatBinding.chat_id == str(user_id)
        ).first()
        if not binding:
            binding = BotChatBinding(
                platform="discord",
                chat_id=str(user_id),
                username=username,
                display_name=display_name
            )
            db_session.add(binding)
        else:
            binding.last_message_at = func.current_timestamp()
            binding.is_active = True
        db_session.commit()

        # Find the shared Bot conversation
        conv = db_session.query(HyperAiConversation).filter(
            HyperAiConversation.is_bot_conversation == True
        ).first()

        if not conv:
            conv = HyperAiConversation(
                title="Hyper AI Bot",
                is_bot_conversation=True
            )
            db_session.add(conv)
            db_session.commit()
            db_session.refresh(conv)

        print(f"[Discord] Using conv id={conv.id}, processing text: {text[:50]}", flush=True)

        # Determine UI language for tool progress messages
        lang = _get_ui_language(db_session)

        # Stream AI response in a thread pool while sending tool progress in real-time.
        # See telegram_bot_service.py _process_polling_message for detailed explanation.
        import asyncio
        loop = asyncio.get_event_loop()

        def process_ai_sync():
            full_resp = ""
            for event in stream_chat_response(db_session, conv.id, text):
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
                        label = _get_tool_label(data["name"], lang)
                        msg = f"【🤖Hyper AI】{label}..."
                        asyncio.run_coroutine_threadsafe(
                            send_discord_message_via_client(user_id, msg), loop
                        )
                    elif event_type == "content":
                        full_resp += data.get("text", "")
                    elif event_type == "error":
                        full_resp = f"Error: {data.get('message', 'Unknown error')}"
                except json.JSONDecodeError:
                    pass
            return full_resp

        full_response = await loop.run_in_executor(None, process_ai_sync)

        print(f"[Discord] AI response length={len(full_response)}", flush=True)
        return full_response

    except Exception as e:
        print(f"[Discord] ERROR: {type(e).__name__}: {e}", flush=True)
        return "Sorry, an error occurred while processing your message."
    finally:
        db_session.close()


@router.post("/discord/disconnect")
async def disconnect_discord_bot(db: Session = Depends(get_db)):
    """Stop Gateway client and disconnect Discord bot."""
    token = get_decrypted_bot_token(db, "discord")
    if not token:
        raise HTTPException(status_code=404, detail="Discord bot not configured")

    await stop_discord_gateway()
    update_bot_status(db, "discord", "disconnected")
    return {"success": True}


@router.get("/discord/status")
def get_discord_status(db: Session = Depends(get_db)):
    """Get Discord bot connection status including Gateway state."""
    config = get_bot_config(db, "discord")
    gateway_running = is_discord_client_running()
    return {
        "config": config,
        "gateway_running": gateway_running,
    }
