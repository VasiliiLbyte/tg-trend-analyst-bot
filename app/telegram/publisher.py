from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.pipeline.compose import PreparedPost, split_telegram_messages
from app.storage.dao import StorageDao

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TelegramPublisher:
    bot_token: str
    channel_id: str
    send_delay_s: float = 0.5
    max_message_len: int = 4096
    max_retry_after_attempts: int = 5

    async def send_digest_post(self, *, dao: StorageDao, post: PreparedPost) -> bool:
        """Returns True when message was posted, False when skipped as duplicate."""
        rendered_text = self._render_post(post)
        claimed_post_id = dao.claim_post_if_new(
            kind=post.kind,
            channel_id=self.channel_id,
            content=rendered_text,
            item_ids=post.item_ids,
        )
        if claimed_post_id is None:
            logger.info(
                "skip_duplicate_post",
                extra={"kind": post.kind, "channel_id": self.channel_id},
            )
            return False

        messages = split_telegram_messages(rendered_text, max_len=self.max_message_len)
        try:
            async with Bot(token=self.bot_token) as bot:
                for msg in messages:
                    await self._send_single_message(bot=bot, text=msg)
                    await asyncio.sleep(self.send_delay_s)
        except Exception:
            dao.mark_post_failed(post_id=claimed_post_id)
            raise

        dao.mark_post_published(post_id=claimed_post_id)
        for item_id in post.item_ids:
            dao.mark_as_posted(item_id=item_id)
        return True

    def _render_post(self, post: PreparedPost) -> str:
        base_text = "\n\n".join(post.messages).strip()
        if post.kind != "digest":
            return base_text
        cta = "\n\n✅ Что делать дальше:\n• Выберите 1 сигнал и проверьте гипотезу за 7 дней.\n• Напишите, какой тренд разобрать глубже."
        if "Что делать дальше" in base_text:
            return base_text
        return f"📊 Тренд-дайджест\n\n{base_text}{cta}".strip()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        retry=retry_if_exception_type(TelegramAPIError),
        reraise=True,
    )
    async def _send_single_message(self, *, bot: Bot, text: str) -> None:
        retry_after_attempts = 0
        while True:
            try:
                await bot.send_message(chat_id=self.channel_id, text=text)
                logger.info("message_sent", extra={"channel": self.channel_id, "len": len(text)})
                return
            except TelegramRetryAfter as e:
                retry_after_attempts += 1
                delay = float(getattr(e, "retry_after", 1.0))
                logger.warning("tg_retry_after", extra={"channel": self.channel_id, "retry_after_s": delay})
                if retry_after_attempts >= self.max_retry_after_attempts:
                    raise
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

