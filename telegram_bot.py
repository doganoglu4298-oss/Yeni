"""
telegram_bot.py
===============
Grid Trading Bot için Telegram Bildirim Modülü

Özellikler:
- Basit mesaj gönderme
- Trade / Risk / Status bildirimleri
- Hata ve önemli olaylar için alert
- python-telegram-bot yerine hafif requests tabanlı (bağımlılık az)

Kullanım:
    from telegram_bot import TelegramNotifier
    tg = TelegramNotifier(config)
    tg.send_message("Bot başladı")
"""

import requests
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram üzerinden bildirim gönderen sınıf.
    """

    def __init__(self, config):
        self.config = config.telegram
        self.enabled = self.config.enabled
        self.bot_token = self.config.bot_token
        self.chat_id = self.config.chat_id

        if self.enabled:
            if "YOUR_TELEGRAM" in self.bot_token or "YOUR_TELEGRAM" in self.chat_id:
                logger.warning("Telegram token/chat_id ayarlanmamış. Bildirimler devre dışı.")
                self.enabled = False
            else:
                logger.info("Telegram bildirimleri aktif.")

    def _send_request(self, text: str) -> bool:
        """Telegram Bot API ile mesaj gönderir"""
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram mesajı gönderilemedi: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram bağlantı hatası: {e}")
            return False

    # =====================================================================
    # KOLAY KULLANIM FONKSİYONLARI
    # =====================================================================
    
    def send_message(self, text: str, prefix: str = "🤖"):
        """Genel mesaj gönderme"""
        if not self.enabled:
            return
        
        full_text = f"{prefix} <b>Grid Bot</b>\n{text}"
        self._send_request(full_text)

    def send_startup(self):
        """Bot başladığında"""
        self.send_message("Bot başlatıldı ✅\nDry-run modu aktif." if self.config.enabled else "Bot başlatıldı (Telegram devre dışı)")

    def send_grid_status(self, status: dict, regime: str, price: float):
        """Grid durumu raporu"""
        msg = (
            f"📊 <b>Grid Durumu</b>\n"
            f"Fiyat: <code>{price}</code>\n"
            f"Rejim: <b>{regime}</b>\n"
            f"Grid Aktif: <b>{status.get('is_active', False)}</b>\n"
            f"Seviye: {status.get('filled_levels', 0)}/{status.get('total_levels', 0)}\n"
            f"Aralık: {status.get('lower_price')} - {status.get('upper_price')}"
        )
        self.send_message(msg, prefix="📈")

    def send_risk_alert(self, reason: str):
        """Risk uyarısı"""
        msg = f"⚠️ <b>RİSK UYARISI</b>\n{reason}"
        self.send_message(msg, prefix="🚨")

    def send_trade_notification(self, side: str, price: float, amount_usdt: float):
        """Emir / İşlem bildirimi"""
        emoji = "🟢" if side.upper() == "BUY" else "🔴"
        msg = (
            f"{emoji} <b>{side.upper()} Emri</b>\n"
            f"Fiyat: <code>{price}</code>\n"
            f"Miktar: <code>{amount_usdt}</code> USDT"
        )
        self.send_message(msg, prefix="💰")

    def send_bot_stop_loss(self, price: float, pnl: float = 0.0):
        """Bot stop loss tetiklendiğinde"""
        msg = (
            f"🛑 <b>BOT STOP LOSS TETİKLENDİ</b>\n"
            f"Fiyat: <code>{price}</code>\n"
            f"Zarar: <code>{pnl}</code> USDT\n"
            f"Bot trading'i durdurdu."
        )
        self.send_message(msg, prefix="🚫")

    def send_daily_summary(self, daily_pnl: float, total_trades: int = 0):
        """Günlük özet"""
        emoji = "🟢" if daily_pnl >= 0 else "🔴"
        msg = (
            f"{emoji} <b>Günlük Özet</b>\n"
            f"PnL: <code>{daily_pnl:.2f}</code> USDT\n"
            f"Toplam İşlem: <code>{total_trades}</code>"
        )
        self.send_message(msg, prefix="📅")

    def send_error(self, error_msg: str):
        """Hata bildirimi"""
        msg = f"❌ <b>HATA</b>\n{error_msg}"
        self.send_message(msg, prefix="🚨")


# =============================================================================
# Basit Test
# =============================================================================

if __name__ == "__main__":
    from config import Config
    
    cfg = Config()
    tg = TelegramNotifier(cfg)
    
    tg.send_message("Test mesajı - Grid Bot Telegram entegrasyonu çalışıyor ✅")