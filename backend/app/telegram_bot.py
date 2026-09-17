import logging
from typing import Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Dispatches trade forecast signals and test alerts to Telegram."""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def update_credentials(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()

    async def send_message(self, text: str, parse_mode: str = "HTML") -> Tuple[bool, str]:
        """Sends an HTML or Markdown message to the configured Telegram chat."""
        if not self.bot_token or not self.chat_id:
            return False, "Telegram Bot Token or Chat ID is not configured."

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if resp.status_code == 200 and data.get("ok"):
                    return True, "Telegram alert delivered successfully."
                else:
                    err_msg = data.get("description", resp.text)
                    logger.error(f"Telegram API error: {err_msg}")
                    if "bot can't initiate conversation" in err_msg.lower():
                        return False, "You need to open your bot in Telegram and press 'START' (or send /start) once so it has permission to message you, then click this button again!"
                    return False, f"Telegram API error: {err_msg}"
        except Exception as e:
            logger.error(f"Failed to connect to Telegram API: {e}")
            return False, f"Connection failed: {str(e)}"

    async def send_test_alert(self) -> Tuple[bool, str]:
        """Sends a test alert to verify Telegram integration."""
        msg = (
            "🤖 <b>AI Quant Trading Forecast Terminal</b>\n\n"
            "✅ <b>Telegram connection verified successfully!</b>\n\n"
            "• Scanning: <i>Gold, Crypto, Indices, Commodities</i>\n"
            "• Horizon: <i>5-Candle Multi-Horizon Prediction (500-bar lookback)</i>\n"
            "• Strategy Filter: <i>Spread &lt; 5% of Stop-Loss distance</i>\n"
            "• Prime Window: <i>London &amp; New York Session Overlap (13:00 - 16:30 UTC)</i>\n\n"
            "You will receive trade notifications here whenever an actionable setup is detected!"
        )
        return await self.send_message(msg)

    async def send_trade_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """Formats and dispatches an actionable trade signal card to Telegram."""
        direction = signal["direction"]
        dir_emoji = "🟢 <b>BUY / LONG</b>" if direction == "BULLISH" else "🔴 <b>SELL / SHORT</b>"
        symbol = signal["symbol"]
        name = signal["name"]
        category = signal["category"]
        tf = signal["timeframe"]
        
        session_icon = "🟢" if signal.get("is_london_ny_overlap") else "🔵"
        session_str = f"{session_icon} {signal.get('session_name', 'Market Open')}"
        
        spread_ratio = signal.get("spread_to_sl_ratio_pct", 0.0)
        spread_status = "✅ &lt; 5% Target Passed" if signal.get("passes_spread_filter") else "⚠️ Elevated Spread"

        msg = (
            f"⚡ <b>AI TRADE SIGNAL DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Asset:</b> {name} (<code>{symbol}</code>)\n"
            f"<b>Category:</b> {category} | <b>Timeframe:</b> {tf}\n"
            f"<b>Direction:</b> {dir_emoji}\n\n"
            f"📊 <b>Trade Execution Levels:</b>\n"
            f"• <b>Entry:</b> <code>{signal['entry_price']}</code>\n"
            f"• <b>Stop-Loss:</b> <code>{signal['stop_loss']}</code> (Risk: {signal['sl_distance']})\n"
            f"• <b>Take-Profit 1:</b> <code>{signal['take_profit_1']}</code> (Reward: {signal['tp_distance']})\n"
            f"• <b>Take-Profit 2 (Ext):</b> <code>{signal['take_profit_2']}</code>\n"
            f"• <b>Risk/Reward Ratio:</b> 1 : <b>{signal['risk_reward_ratio']}</b>\n\n"
            f"🛡️ <b>Risk &amp; Session Confluence:</b>\n"
            f"• <b>Spread vs SL Ratio:</b> <code>{spread_ratio}%</code> ({spread_status})\n"
            f"• <b>Session:</b> {session_str}\n"
            f"• <b>AI Conviction:</b> <b>{signal['conviction']}%</b>\n"
            f"• <b>Exp. 5-Candle Return:</b> <code>{signal['expected_return_pct']:+0.2f}%</code>\n"
            f"• <b>Engine:</b> <i>{signal.get('model_used', 'Chronos AI')}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ <i>{signal['timestamp']}</i>"
        )
        return await self.send_message(msg)


# Global telegram notifier instance
telegram_notifier = TelegramNotifier()
