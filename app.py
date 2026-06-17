"""
app.py – DatemexBot  |  Anonymous Chat Bot
Main entry point: wires all handlers together.
"""

import logging
import time
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

import database as db
import utils
import admin as adm
from config import (
    BOT_TOKEN, LOG_LEVEL,
    AGE, GENDER, COUNTRY, STATE_IN,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRATION  CONVERSATION
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    if db.is_banned(user.id):
        await update.message.reply_text("⛔ You have been banned from this bot.")
        return ConversationHandler.END

    # Already registered? Skip straight to chat prompt
    if db.is_registered(user.id):
        keyboard = [[InlineKeyboardButton("💬 Start Chatting", callback_data="go_chat")]]
        await update.message.reply_text(
            f"👋 Welcome back, <b>{user.first_name}</b>!\n\n"
            "Your profile is already set up. Ready to meet someone?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🌟 <b>Welcome to DatemexBot!</b>\n\n"
        "Let's set up your profile in a few quick steps.\n\n"
        "How old are you? (e.g. 23)",
        parse_mode=ParseMode.HTML
    )
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    age_text = update.message.text.strip()
    if not age_text.isdigit() or not (13 <= int(age_text) <= 99):
        await update.message.reply_text("❌ Please enter a valid age (13–99):")
        return AGE

    context.user_data["age"] = age_text
    keyboard = [
        [InlineKeyboardButton("👱‍♂️ Male", callback_data="Male"),
         InlineKeyboardButton("👩 Female", callback_data="Female"),
         InlineKeyboardButton("⚧ Other", callback_data="Other")]
    ]
    await update.message.reply_text("Select your gender:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["gender"] = query.data

    country_rows = [
        ["🇮🇳 India", "🇺🇸 America", "🇬🇧 UK", "🇨🇦 Canada"],
        ["🇦🇺 Australia", "🇩🇪 Germany", "🇫🇷 France", "🇯🇵 Japan"],
        ["🇧🇷 Brazil", "🇷🇺 Russia", "🇨🇳 China", "🇰🇷 South Korea"],
        ["🇮🇩 Indonesia", "🇸🇦 Saudi Arabia", "🇮🇷 Iran", "🇳🇬 Nigeria"],
        ["🇪🇸 Spain", "🇮🇹 Italy", "🇲🇾 Malaysia", "🇵🇰 Pakistan"],
        ["🇿🇦 South Africa", "🇪🇹 Ethiopia", "🇦🇷 Argentina", "🇪🇬 Egypt"],
    ]

    buttons = [
        [InlineKeyboardButton(label, callback_data=label.split(" ", 1)[1])
         for label in row]
        for row in country_rows
    ]
    await query.edit_message_text("🌍 Select your country:", reply_markup=InlineKeyboardMarkup(buttons))
    return COUNTRY


async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    country = query.data
    context.user_data["country"] = country

    if country == "India":
        indian_states = [
            "Andaman & Nicobar", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
            "Bihar", "Chandigarh", "Chhattisgarh", "Dadra & Nagar Haveli",
            "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
            "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh",
            "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
            "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan",
            "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
            "Uttarakhand", "West Bengal"
        ]
        btns = [
            [InlineKeyboardButton(indian_states[i], callback_data=indian_states[i])] +
            ([InlineKeyboardButton(indian_states[i+1], callback_data=indian_states[i+1])]
             if i+1 < len(indian_states) else [])
            for i in range(0, len(indian_states), 2)
        ]
        await query.edit_message_text("🇮🇳 Select your state:", reply_markup=InlineKeyboardMarkup(btns))
        return STATE_IN
    else:
        _finish_registration(query.from_user.id, context, country)
        await _send_registration_success(query)
        return ConversationHandler.END


async def get_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    state = query.data
    _finish_registration(query.from_user.id, context, f"India - {state}")
    await _send_registration_success(query)
    return ConversationHandler.END


def _finish_registration(user_id: int, context: ContextTypes.DEFAULT_TYPE, location: str):
    db.set_profile(
        user_id,
        age=context.user_data["age"],
        gender=context.user_data["gender"],
        state=location
    )


async def _send_registration_success(query):
    keyboard = [[InlineKeyboardButton("💬 Start Chatting Now!", callback_data="go_chat")]]
    await query.edit_message_text(
        "✅ <b>Profile registered successfully!</b>\n\n"
        "You're all set. Tap below to find a chat partner 👇",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Registration cancelled. Type /start to try again.")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
#  CHAT COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await _start_matching(user_id, update, context)


async def _start_matching(user_id: int, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.is_banned(user_id):
        await _reply(update, context, user_id, "⛔ You have been banned from this bot.")
        return

    if not db.is_registered(user_id):
        await _reply(update, context, user_id, "⚠️ Please register first by typing /start")
        return

    row = db.get_user(user_id)
    if row and row["partner_id"]:
        await _reply(update, context, user_id, "ℹ️ You are already connected to a partner!")
        return

    if user_id in utils.queue:
        await _reply(update, context, user_id, "🔎 Still searching… please wait.")
        return

    if utils.queue:
        partner_id = utils.queue.pop(0)
        session_id = utils.generate_session_tag()

        db.set_partner(user_id, partner_id, session_id)
        db.set_partner(partner_id, user_id, session_id)

        partner_row = db.get_user(partner_id)
        user_row    = db.get_user(user_id)

        await context.bot.send_message(user_id,    utils.build_match_card(partner_row), parse_mode=ParseMode.HTML)
        await context.bot.send_message(partner_id, utils.build_match_card(user_row),    parse_mode=ParseMode.HTML)
    else:
        utils.queue.append(user_id)
        await _reply(update, context, user_id,
                     "🔎 Looking for a partner… please wait.\n\nType /exit to cancel the search.")


async def cmd_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = db.get_user(user_id)
    if not row:
        return

    partner_id = row["partner_id"]
    session_id = row["last_session"]

    if partner_id:
        db.set_partner(user_id, None, None)
        db.set_partner(partner_id, None, None)
        card = utils.build_disconnect_card(session_id or "N/A")
        keyboard = [[InlineKeyboardButton("⚠️ Report", callback_data=f"report_{session_id}")]]
        rm = InlineKeyboardMarkup(keyboard)
        try:
            await update.message.reply_text(card, parse_mode=ParseMode.HTML, reply_markup=rm)
        except Exception:
            pass
        try:
            await context.bot.send_message(partner_id, card, parse_mode=ParseMode.HTML, reply_markup=rm)
        except Exception:
            pass
    elif user_id in utils.queue:
        utils.queue.remove(user_id)
        await update.message.reply_text("🔍 Search cancelled.")
    else:
        await update.message.reply_text("ℹ️ You are not in a chat right now.")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = db.get_user(user_id)
    if not row:
        return

    partner_id = row["partner_id"]
    session_id = row["last_session"]

    if partner_id:
        db.set_partner(user_id, None, None)
        db.set_partner(partner_id, None, None)
        card = utils.build_disconnect_card(session_id or "N/A")
        keyboard = [[InlineKeyboardButton("⚠️ Report", callback_data=f"report_{session_id}")]]
        try:
            await context.bot.send_message(
                partner_id, card, parse_mode=ParseMode.
