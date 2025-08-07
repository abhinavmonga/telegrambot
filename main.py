import json
import os
import logging
from datetime import datetime
import pytz
import random

from telegram import Update, InputFile
from telegram.error import TelegramError, BadRequest
from telegram.ext import (Updater, MessageHandler, Filters, CallbackContext,
                          CommandHandler)

try:
    from keep_alive import keep_alive
    keep_alive()
except:
    pass

BOT_TOKEN = '7735201778:AAF2DTBWYvPUSyHzSsflKyHWRb_8ednBInE'
ADMIN_IDS = [5999146737, 8149953803]

FORWARD_MAP_FILE = 'forward_map.json'
USER_DB_FILE = 'users.json'
SHORTCUTS_FILE = 'shortcuts.json'

logging.basicConfig(level=logging.INFO)

RENTAL_MESSAGE = (
    "📢 *Hi*,\n\n"
    "We are currently in need of renting a large number of WhatsApp accounts for customer service. "
    "If your WhatsApp account is idle, you can rent it to us.\n\n"
    "💸 Our current offer is to pay you *₹80 per task* after logging into our customer service system. "
    "We pay via *bank transfer or UPI*.\n\n"
    "Are you interested?")


def save_forward_mapping(msg_id, user_id):
    mapping = load_forward_mapping()
    mapping[str(msg_id)] = user_id
    with open(FORWARD_MAP_FILE, 'w') as f:
        json.dump(mapping, f, indent=4)


def load_forward_mapping():
    if os.path.exists(FORWARD_MAP_FILE):
        try:
            with open(FORWARD_MAP_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_users(users_set):
    with open(USER_DB_FILE, "w") as f:
        json.dump(list(users_set), f, indent=4)


def load_shortcuts():
    if os.path.exists(SHORTCUTS_FILE):
        with open(SHORTCUTS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_shortcuts(shortcuts_dict):
    with open(SHORTCUTS_FILE, 'w') as f:
        json.dump(shortcuts_dict, f, indent=4)


def add_shortcut(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return

    if len(context.args) < 2:
        update.message.reply_text(
            "❌ *Invalid format.*\n\n"
            "Please use: `/addshortcut <name> <message>`\n"
            "*Example:* `/addshortcut welcome Hello! We will get back to you soon.`",
            parse_mode="Markdown")
        return

    name = context.args[0].lower()
    message = " ".join(context.args[1:])

    shortcuts = load_shortcuts()
    shortcuts[name] = message
    save_shortcuts(shortcuts)

    confirmation_text = (f"✅ *Shortcut created successfully!*\n"
                         f"──────────────────\n"
                         f"🏷️ *Command:* `/{name}`\n"
                         f"💬 *Message:*\n```\n{message}\n```")
    update.message.reply_text(confirmation_text, parse_mode="Markdown")


def list_shortcuts(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return

    shortcuts = load_shortcuts()
    if not shortcuts:
        update.message.reply_text(
            "🤷‍♀️ No shortcuts have been created yet. Use `/addshortcut` to create one."
        )
        return

    message_parts = ["📋 *Here are your saved shortcuts:*\n"]
    for name, text in shortcuts.items():
        shortcut_card = (f"──────────────────\n"
                         f"🏷️ *Command:* `/{name}`\n"
                         f"💬 *Message:*\n```\n{text}\n```")
        message_parts.append(shortcut_card)

    final_message = "\n".join(message_parts)
    update.message.reply_text(final_message, parse_mode="Markdown")


def delete_shortcut(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return

    if not context.args:
        update.message.reply_text(
            "Please specify the shortcut name to delete. Example: `/deleteshortcut welcome`"
        )
        return

    name = context.args[0].lower()
    shortcuts = load_shortcuts()

    if name in shortcuts:
        del shortcuts[name]
        save_shortcuts(shortcuts)
        update.message.reply_text(f"✅ Shortcut `/{name}` has been deleted.",
                                  parse_mode="Markdown")
    else:
        update.message.reply_text(f"❌ Shortcut `/{name}` not found.",
                                  parse_mode="Markdown")


def handle_dynamic_shortcut(update: Update, context: CallbackContext):
    """
    Handles execution of shortcuts. If Markdown parsing fails, it sends the message as plain text.
    """
    if update.message.chat_id not in ADMIN_IDS:
        return

    command = update.message.text.lstrip('/').split('@')[0].lower()
    shortcuts = load_shortcuts()

    if command in shortcuts:
        if not update.message.reply_to_message:
            update.message.reply_text(
                f"❗ To use the `/{command}` shortcut, you must *reply* to a user's forwarded message.",
                parse_mode="Markdown")
            return

        forward_map = load_forward_mapping()
        original_msg_id = str(update.message.reply_to_message.message_id)

        if original_msg_id not in forward_map:
            update.message.reply_text(
                "❌ Couldn't find the original user for this message.")
            return

        user_id = forward_map[original_msg_id]
        message_to_send = shortcuts[command]

        try:
            # First, try to send with Markdown formatting
            context.bot.send_message(chat_id=user_id,
                                     text=message_to_send,
                                     parse_mode="Markdown")
            update.message.reply_text(
                f"✅ Shortcut `/{command}` sent to user `{user_id}`.",
                parse_mode="Markdown")

        except BadRequest as e:
            # If Markdown parsing fails, send as plain text
            if "Can't parse entities" in str(e):
                try:
                    context.bot.send_message(chat_id=user_id,
                                             text=message_to_send,
                                             parse_mode=None)
                    update.message.reply_text(
                        f"⚠️ Shortcut `/{command}` sent as plain text due to a formatting error.",
                        parse_mode="Markdown")
                except TelegramError as final_e:
                    update.message.reply_text(
                        f"❌ Failed to send message even as plain text. Error: {final_e}"
                    )
            else:
                update.message.reply_text(
                    f"❌ An unexpected error occurred: {e}")

        except TelegramError as e:
            # Handle other errors like user blocking the bot
            if "Forbidden" in str(e) or "Chat not found" in str(e):
                update.message.reply_text(
                    f"❌ Failed to send message. User `{user_id}` may have blocked the bot.",
                    parse_mode="Markdown")
                users = load_users()
                if user_id in users:
                    users.remove(user_id)
                    save_users(users)
            else:
                update.message.reply_text(f"❌ An error occurred: {e}")
    else:
        update.message.reply_text(
            f"🤷‍♀️ Unknown command: `/{command}`.\nUse `/addshortcut` to create it or `/listshortcuts` to see available shortcuts.",
            parse_mode="Markdown")


def send_rental_offer(context: CallbackContext):
    job = context.job
    user_id = job.context
    users = load_users()

    try:
        context.bot.send_message(chat_id=user_id,
                                 text=RENTAL_MESSAGE,
                                 parse_mode="Markdown")
    except TelegramError as e:
        if "Forbidden" in str(e) or "Chat not found" in str(e):
            if user_id in users:
                users.remove(user_id)
                save_users(users)


def send_users_file(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return

    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'rb') as f:
            update.message.reply_document(
                document=InputFile(f, filename='users.json'))
    else:
        update.message.reply_text("❌ users.json file not found.")


def handle_user_message(update: Update, context: CallbackContext):
    if update.message is None:
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name

    users = load_users()
    is_new_user = user_id not in users
    if is_new_user:
        users.add(user_id)
        save_users(users)

        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        try:
            if now.hour >= 17:
                context.bot.send_message(
                    chat_id=user_id,
                    text=
                    "🕔 We're off work now. Please come back tomorrow to earn money.",
                    parse_mode="Markdown")
            else:
                context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ *Please wait, we will respond shortly.*",
                    parse_mode="Markdown")
                delay = random.randint(15, 20)
                context.job_queue.run_once(send_rental_offer,
                                           delay,
                                           context=user_id)
        except TelegramError as e:
            if "Forbidden" in str(e) or "Chat not found" in str(e):
                users.remove(user_id)
                save_users(users)

    ist = pytz.timezone('Asia/Kolkata')
    timestamp = datetime.now(ist).strftime("%Y-%m-%d %H:%M %p IST")

    base_info = (f"📬 *New Message Received*\n\n"
                 f"👤 *User:* @{username} (ID: `{user_id}`)\n"
                 f"🗓️ *Time:* {timestamp}")

    reply_context = ""
    if update.message.reply_to_message:
        original_text = update.message.reply_to_message.text or "[Media]"
        truncated_text = (original_text[:70] +
                          '...') if len(original_text) > 70 else original_text
        reply_context = f"\n\n↪️ *In Reply To:*\n_{truncated_text}_"

    for admin_id in ADMIN_IDS:
        try:
            if update.message.text:
                message_text = f"{base_info}{reply_context}\n\n💬 *Message:*\n{update.message.text}"
                sent_msg = context.bot.send_message(chat_id=admin_id,
                                                    text=message_text,
                                                    parse_mode='Markdown')
                save_forward_mapping(sent_msg.message_id, user_id)
            elif update.message.photo:
                caption = update.message.caption or ""
                message_text = f"{base_info}{reply_context}\n\n🖼️ *Photo Received*\n{caption}"
                sent_msg = context.bot.send_photo(
                    chat_id=admin_id,
                    photo=update.message.photo[-1].file_id,
                    caption=message_text,
                    parse_mode='Markdown')
                save_forward_mapping(sent_msg.message_id, user_id)
            elif update.message.document:
                caption = update.message.caption or ""
                message_text = f"{base_info}{reply_context}\n\n📎 *Document Received*\n{caption}"
                sent_msg = context.bot.send_document(
                    chat_id=admin_id,
                    document=update.message.document.file_id,
                    caption=message_text,
                    parse_mode='Markdown')
                save_forward_mapping(sent_msg.message_id, user_id)
            elif update.message.video:
                caption = update.message.caption or ""
                message_text = f"{base_info}{reply_context}\n\n🎥 *Video Received*\n{caption}"
                sent_msg = context.bot.send_video(
                    chat_id=admin_id,
                    video=update.message.video.file_id,
                    caption=message_text,
                    parse_mode='Markdown')
                save_forward_mapping(sent_msg.message_id, user_id)

        except Exception as e:
            logging.error(f"Error forwarding to admin {admin_id}: {e}")


def handle_admin_reply(update: Update, context: CallbackContext):
    sender_id = update.message.chat_id
    if sender_id not in ADMIN_IDS:
        return

    reply_to = update.message.reply_to_message
    if not reply_to:
        update.message.reply_text(
            "❗Please reply to a user's forwarded message.")
        return

    forward_map = load_forward_mapping()
    original_msg_id = str(reply_to.message_id)

    if original_msg_id not in forward_map:
        update.message.reply_text("❌ Couldn't find the original user.")
        return

    user_id = forward_map[original_msg_id]

    try:
        if update.message.text:
            context.bot.send_message(chat_id=user_id, text=update.message.text)
        elif update.message.photo:
            context.bot.send_photo(chat_id=user_id,
                                   photo=update.message.photo[-1].file_id,
                                   caption=update.message.caption or "")
        elif update.message.document:
            context.bot.send_document(chat_id=user_id,
                                      document=update.message.document.file_id,
                                      caption=update.message.caption or "")
        elif update.message.video:
            context.bot.send_video(chat_id=user_id,
                                   video=update.message.video.file_id,
                                   caption=update.message.caption or "")

        for admin_id in ADMIN_IDS:
            if admin_id != sender_id:
                context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Admin {sender_id} replied to user `{user_id}`.",
                    parse_mode="Markdown")

    except TelegramError as e:
        if "Forbidden" in str(e) or "Chat not found" in str(e):
            users = load_users()
            if user_id in users:
                users.remove(user_id)
                save_users(users)


def broadcast_to_all(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return

    users = load_users()
    sent_count = 0
    failed_count = 0

    content_to_send = ""
    raw_text = update.message.text or update.message.caption
    if raw_text:
        try:
            content_to_send = raw_text.split(' ', 1)[1]
        except IndexError:
            pass

    if update.message.text and not content_to_send:
        update.message.reply_text(
            "❗Please provide a message after the command.\n*Example:* `/broadcast Hello everyone!`",
            parse_mode="Markdown")
        return

    status_msg = update.message.reply_text(
        f"🚀 Starting broadcast to {len(users)} users...")

    for uid in users.copy():
        try:
            if update.message.video:
                context.bot.send_video(chat_id=uid,
                                       video=update.message.video.file_id,
                                       caption=content_to_send,
                                       parse_mode="Markdown")
            elif update.message.photo:
                context.bot.send_photo(chat_id=uid,
                                       photo=update.message.photo[-1].file_id,
                                       caption=content_to_send,
                                       parse_mode="Markdown")
            elif update.message.document:
                context.bot.send_document(
                    chat_id=uid,
                    document=update.message.document.file_id,
                    caption=content_to_send,
                    parse_mode="Markdown")
            elif update.message.text:
                if content_to_send:
                    context.bot.send_message(chat_id=uid,
                                             text=content_to_send,
                                             parse_mode="Markdown")

            sent_count += 1
        except TelegramError as e:
            failed_count += 1
            if "Forbidden" in str(e) or "Chat not found" in str(e):
                users.remove(uid)
                save_users(users)

    context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=status_msg.message_id,
        text=
        f"✅ *Broadcast Complete*\n\nSent: {sent_count}\nFailed: {failed_count}\nActive Users: {len(users)}",
        parse_mode="Markdown")


def count_users(update: Update, context: CallbackContext):
    if update.message.chat_id not in ADMIN_IDS:
        return
    users = load_users()
    update.message.reply_text(f"👥 Total unique users: {len(users)}")


def main():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("broadcast", broadcast_to_all))
    dp.add_handler(CommandHandler("countusers", count_users))
    dp.add_handler(CommandHandler("getusers", send_users_file))

    dp.add_handler(CommandHandler("addshortcut", add_shortcut))
    dp.add_handler(CommandHandler("listshortcuts", list_shortcuts))
    dp.add_handler(CommandHandler("deleteshortcut", delete_shortcut))

    dp.add_handler(
        MessageHandler(
            Filters.chat_type.private &
            (Filters.text | Filters.photo | Filters.document | Filters.video) &
            (~Filters.user(user_id=ADMIN_IDS)), handle_user_message))

    dp.add_handler(
        MessageHandler(
            Filters.chat_type.private &
            (Filters.text | Filters.photo | Filters.document | Filters.video)
            & Filters.user(user_id=ADMIN_IDS) & (~Filters.command),
            handle_admin_reply))

    dp.add_handler(
        MessageHandler(Filters.command & Filters.user(user_id=ADMIN_IDS),
                       handle_dynamic_shortcut))

    print("✅ Bot is running with custom shortcut feature...")
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
