from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.pipeline.compose import PreparedPost

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TelegramPublisher:
    bot_token: str
    channel_id: str
    send_delay_s: float = 0.5

    async def publish_post(self, post: PreparedPost) -> None:
        async with Bot(token=self.bot_token) as bot:
            for msg in post.messages:
                await self._send_with_retry(bot=bot, text=msg)
                await asyncio.sleep(self.send_delay_s)

    async def _send_with_retry(self, *, bot: Bot, text: str) -> None:
        while True:
            try:
                await bot.send_message(chat_id=self.channel_id, text=text)
                logger.info("message_sent", extra={"channel": self.channel_id, "len": len(text)})
                return
            except TelegramRetryAfter as e:
                delay = float(getattr(e, "retry_after", 1.0))
                logger.warning("tg_retry_after", extra={"channel": self.channel_id, "retry_after_s": delay})
                await asyncio.sleep(delay)
            except TelegramForbiddenError as e:
                logger.error("tg_forbidden", extra={"channel": self.channel_id, "err": str(e)})
                raise
            except TelegramBadRequest as e:
                logger.error("tg_bad_request", extra={"channel": self.channel_id, "err": str(e)})
                raise
            except TelegramAPIError as e:
                logger.error("tg_api_error", extra={"channel": self.channel_id, "err": str(e)})
                raise

