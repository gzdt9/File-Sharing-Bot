#(©)Codexbotz

import asyncio
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, StopPropagation

from bot import Bot
from config import ADMINS, CHANNEL_ID, DISABLE_CHANNEL_BUTTON
from helper_func import encode
from database.database import create_file_code, get_file_message_id


UPLOAD_MEDIA = filters.video | filters.document


@Bot.on_message(filters.private & UPLOAD_MEDIA)
async def user_upload(client: Client, message: Message):
    """Store files sent in private chat and give every uploader a pickup code."""
    reply_text = await message.reply_text("正在保存文件…", quote=True)
    try:
        post_message = await message.copy(
            chat_id=client.db_channel.id,
            disable_notification=True,
        )
        code = await create_file_code(post_message.id)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        post_message = await message.copy(
            chat_id=client.db_channel.id,
            disable_notification=True,
        )
        code = await create_file_code(post_message.id)
    except Exception as e:
        print(e)
        await reply_text.edit_text("保存失败，请稍后再试。")
        raise StopPropagation

    await reply_text.edit_text(
        f"✅ 已保存到存储频道。\n\n取件码：<code>{code}</code>\n"
        "把取件码发给需要领取的人；对方在机器人私聊中直接发送该取件码即可获取文件。"
    )
    raise StopPropagation


@Bot.on_message(filters.private & filters.text)
async def pickup_by_code(client: Client, message: Message):
    """Return a stored file when someone sends its pickup code in a private chat."""
    code = message.text.strip().upper().replace(' ', '')
    if len(code) != 8 or not code.isalnum():
        return
    message_id = await get_file_message_id(code)
    if not message_id:
        return
    try:
        stored_message = await client.get_messages(client.db_channel.id, message_id)
        await stored_message.copy(chat_id=message.chat.id)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        stored_message = await client.get_messages(client.db_channel.id, message_id)
        await stored_message.copy(chat_id=message.chat.id)
    except Exception as e:
        print(e)
        await message.reply_text("取件失败：文件可能已被删除，请联系上传者。")
    raise StopPropagation

@Bot.on_message(filters.private & filters.user(ADMINS) & ~UPLOAD_MEDIA & ~filters.command(['start','users','broadcast','batch','genlink','stats']))
async def channel_post(client: Client, message: Message):
    reply_text = await message.reply_text("Please Wait...!", quote = True)
    try:
        post_message = await message.copy(chat_id = client.db_channel.id, disable_notification=True)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        post_message = await message.copy(chat_id = client.db_channel.id, disable_notification=True)
    except Exception as e:
        print(e)
        await reply_text.edit_text("Something went Wrong..!")
        return
    converted_id = post_message.id * abs(client.db_channel.id)
    string = f"get-{converted_id}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])

    await reply_text.edit(f"<b>Here is your link</b>\n\n{link}", reply_markup=reply_markup, disable_web_page_preview = True)

    if not DISABLE_CHANNEL_BUTTON:
        try:
            await post_message.edit_reply_markup(reply_markup)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await post_message.edit_reply_markup(reply_markup)
        except Exception:
            pass

@Bot.on_message(filters.channel & filters.incoming & filters.chat(CHANNEL_ID))
async def new_post(client: Client, message: Message):

    if DISABLE_CHANNEL_BUTTON:
        return

    converted_id = message.id * abs(client.db_channel.id)
    string = f"get-{converted_id}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    try:
        await message.edit_reply_markup(reply_markup)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.edit_reply_markup(reply_markup)
    except Exception:
        pass
