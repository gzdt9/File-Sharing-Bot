"""Telegram Bot API implementation for private-channel file sharing.

This version intentionally does not use Telegram's MTProto API, so it needs no
APP_ID or API_HASH.  Files are copied by the Bot API into the configured
private storage channel and indexed in MongoDB by an unguessable pickup code.
"""

import logging
import os
import secrets

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


load_dotenv()
TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
DB_URI = os.environ.get("DATABASE_URL", "")
DB_NAME = os.environ.get("DATABASE_NAME", "videobot")

if not TOKEN or not CHANNEL_ID or not DB_URI:
    raise RuntimeError(
        "Missing TG_BOT_TOKEN, CHANNEL_ID, or DATABASE_URL environment variable."
    )

mongo = MongoClient(DB_URI)
database = mongo[DB_NAME]
codes = database["file_codes"]
users = database["users"]
codes.create_index("code", unique=True)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def store_code(message_id: int) -> str:
    for _ in range(20):
        code = new_code()
        try:
            codes.insert_one({"code": code, "message_id": message_id})
            return code
        except DuplicateKeyError:
            continue
    raise RuntimeError("Could not generate a unique pickup code")


async def remember_user(update: Update) -> None:
    if update.effective_user:
        users.update_one({"_id": update.effective_user.id}, {"$set": {}}, upsert=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await remember_user(update)
    argument = context.args[0].upper() if context.args else ""
    if argument.startswith("F_"):
        await deliver_code(update, argument[2:])
        return
    await update.effective_message.reply_text(
        "发送视频或文件给我，我会保存到存储频道并返回取件码。\n\n"
        "领取文件：直接把 8 位取件码发给我，或打开分享链接。"
    )


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await remember_user(update)
    message = update.effective_message
    progress = await message.reply_text("正在保存文件…")
    try:
        saved = await message.copy(chat_id=CHANNEL_ID, disable_notification=True)
        code = store_code(saved.message_id)
        username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{username}?start=f_{code}"
        await progress.edit_text(
            f"✅ 已保存到存储频道。\n\n"
            f"取件码：<code>{code}</code>\n"
            f"分享链接：{share_link}\n\n"
            "把取件码或链接发给需要领取的人即可。"
        )
    except Exception:
        logging.exception("Saving a file failed")
        await progress.edit_text("保存失败，请稍后再试。")


async def deliver_code(update: Update, code: str) -> None:
    message = update.effective_message
    normalized = code.strip().upper().replace(" ", "")
    if len(normalized) != 8 or not normalized.isalnum():
        return
    record = codes.find_one({"code": normalized})
    if not record:
        return
    try:
        await message.get_bot().copy_message(
            chat_id=message.chat_id,
            from_chat_id=CHANNEL_ID,
            message_id=record["message_id"],
        )
    except Exception:
        logging.exception("Delivering a file failed")
        await message.reply_text("取件失败：文件可能已被删除，请联系上传者。")


async def pickup_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await deliver_code(update, update.effective_message.text or "")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not OWNER_ID or update.effective_user.id != OWNER_ID:
        return
    await update.effective_message.reply_text(f"用户数：{users.count_documents({})}")


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    application = Application.builder().token(TOKEN).build()
    private = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats, filters=private))
    application.add_handler(
        MessageHandler(private & (filters.VIDEO | filters.Document.ALL), receive_file)
    )
    application.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, pickup_text))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
