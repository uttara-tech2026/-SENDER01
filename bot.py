"""
Media -> Admin relay bot.

Anyone sends a photo or video to the bot. The bot:
  1. Checks it against everything it's seen before (Telegram's
     file_unique_id), and silently drops it if it's a duplicate.
  2. Otherwise queues it for relay to the admin.

A single background worker drains that queue and forwards items to
ADMIN_ID one at a time, waiting RELAY_DELAY_SECONDS between each send,
so a burst of incoming media arrives as a steady, rate-limit-safe
stream rather than all at once.

No commands, no captions, no per-user setup -- the sender doesn't need
to type anything at all, just send the media.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import config
import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Queue of {"type": "photo"|"video", "file_id": str} waiting to be relayed.
relay_queue: "asyncio.Queue[dict]" = asyncio.Queue()


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    if message.photo:
        media_type = "photo"
        # photo is a list of sizes, largest last
        file_id = message.photo[-1].file_id
        unique_id = message.photo[-1].file_unique_id
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
        unique_id = message.video.file_unique_id
    else:
        return  # ignore text/documents/stickers/etc.

    is_new = await storage.check_and_mark(unique_id)
    if not is_new:
        logger.info(f"Dropped duplicate {media_type} ({unique_id})")
        return

    await relay_queue.put({"type": media_type, "file_id": file_id})
    logger.info(f"Queued {media_type} for relay ({unique_id})")


async def relay_worker(app: Application):
    """Drains relay_queue forever, sending one item to the admin every
    RELAY_DELAY_SECONDS. Runs as a background task for the app's
    lifetime."""
    bot = app.bot
    while True:
        item = await relay_queue.get()
        try:
            if item["type"] == "photo":
                await bot.send_photo(config.ADMIN_ID, item["file_id"])
            else:
                await bot.send_video(config.ADMIN_ID, item["file_id"])
        except Exception as e:
            logger.error(f"Failed to relay {item['type']} to admin: {e}")
        finally:
            relay_queue.task_done()
        await asyncio.sleep(config.RELAY_DELAY_SECONDS)


async def post_init(app: Application):
    app.create_task(relay_worker(app))
    logger.info("🤖 Bot running...")


def main():
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    app.run_polling()


if __name__ == "__main__":
    main()
