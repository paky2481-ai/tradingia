"""
Notification system: Telegram + Email
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="notifications")


class Notifier:
    """Send alerts via Telegram and Email."""

    def __init__(self):
        self.cfg = settings.notifications
        self._tg_bot = None

    async def _get_tg_bot(self):
        if self._tg_bot is None and self.cfg.telegram_token:
            try:
                from telegram import Bot
                self._tg_bot = Bot(token=self.cfg.telegram_token)
            except Exception as e:
                logger.warning(f"Telegram init error: {e}")
        return self._tg_bot

    async def send_telegram(self, message: str):
        if not self.cfg.telegram_token or not self.cfg.telegram_chat_id:
            return
        bot = await self._get_tg_bot()
        if bot is None:
            return
        try:
            await bot.send_message(
                chat_id=self.cfg.telegram_chat_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

    async def send_email(self, subject: str, body: str):
        if not self.cfg.email_smtp or not self.cfg.email_from:
            return
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.cfg.email_from
            msg["To"] = self.cfg.email_to
            await asyncio.to_thread(self._send_email_sync, msg)
        except Exception as e:
            logger.error(f"Email send error: {e}")

    def _send_email_sync(self, msg):
        with smtplib.SMTP_SSL(self.cfg.email_smtp, 465) as server:
            server.login(self.cfg.email_from, self.cfg.email_password)
            server.sendmail(self.cfg.email_from, self.cfg.email_to, msg.as_string())

    async def notify_trade(self, symbol: str, direction: str, quantity: float, price: float, pnl: Optional[float] = None):
        if not self.cfg.notify_on_trade:
            return
        emoji = "🟢" if direction == "buy" else "🔴"
        msg = (
            f"<b>TradingIA {emoji} TRADE</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Direction: <b>{direction.upper()}</b>\n"
            f"Quantity: {quantity:.4f}\n"
            f"Price: {price:.5f}"
        )
        if pnl is not None:
            msg += f"\nP&L: <b>{pnl:+.2f}</b>"
        await self.send_telegram(msg)

    async def notify_alert(self, title: str, message: str):
        if not self.cfg.notify_on_alert:
            return
        full_msg = f"<b>⚠️ TradingIA Alert: {title}</b>\n{message}"
        await self.send_telegram(full_msg)
        await self.send_email(f"TradingIA Alert: {title}", message)


notifier = Notifier()
