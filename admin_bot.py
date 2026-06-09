"""
Admin Bot — သင့် Telegram ဆီ payment confirmation ရောက်လာပြီး
confirm / reject လုပ်နိုင်တယ်။

Railway မှာ ADMIN_CHAT_ID variable ထည့်ပါ။
bot.py နဲ့ တစ်ခါတည်း run သည် — bot.py ၏ main() မှ app ကို import လုပ်သုံးတယ်။
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
import database as db

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
KPAY_NUMBER = os.getenv("KPAY_NUMBER", "09xxxxxxxxx")
WAVE_NUMBER = os.getenv("WAVE_NUMBER", "09xxxxxxxxx")

PLANS = {
    "1": {"months": 1, "price": 5000, "label": "၁ လ — MMK 5,000"},
    "3": {"months": 3, "price": 13000, "label": "၃ လ — MMK 13,000 (သက်သာ)"},
    "6": {"months": 6, "price": 25000, "label": "၆ လ — MMK 25,000 (အသက်သာဆုံး)"},
}

async def send_payment_to_admin(context, payment_id, uid, months, amount, screenshot_file_id):
    """Admin ဆီ payment notification ပို့တယ်"""
    if not ADMIN_CHAT_ID:
        logger.error("ADMIN_CHAT_ID မရှိပါ!")
        return

    user_info = f"User ID: <code>{uid}</code>"
    plan_info = f"Plan: {months} လ — MMK {amount:,}"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Confirm (#{payment_id})", callback_data=f"admin_confirm_{payment_id}"),
         InlineKeyboardButton(f"❌ Reject (#{payment_id})", callback_data=f"admin_reject_{payment_id}")]
    ])

    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=screenshot_file_id,
        caption=f"💰 <b>Payment Request #{payment_id}</b>\n\n{user_info}\n{plan_info}",
        parse_mode="HTML",
        reply_markup=kb
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ရဲ့ confirm/reject ခလုတ် handle လုပ်တယ်"""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_CHAT_ID:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    if query.data.startswith("admin_confirm_"):
        payment_id = int(query.data.replace("admin_confirm_", ""))
        payment = db.get_pending_payment(payment_id)
        if not payment:
            await query.edit_message_caption("❌ Payment မတွေ့ပါ။")
            return

        uid = payment[1]
        months = payment[3]
        new_expire = db.activate_premium(uid, months)
        db.update_payment_status(payment_id, "confirmed")

        # User ဆီ notify
        lang = db.get_language(uid)
        if lang == "MM":
            user_msg = (f"🎉 <b>Premium Activated!</b>\n\n"
                       f"✅ {months} လ Premium အတည်ပြုပြီးပါပြီ။\n"
                       f"📅 သက်တမ်းကုန်ဆုံးရက်: {new_expire.strftime('%Y-%m-%d')}\n\n"
                       f"Premium features အားလုံး အသုံးပြုနိုင်ပါပြီ! 🚗⚡")
        else:
            user_msg = (f"🎉 <b>Premium Activated!</b>\n\n"
                       f"✅ {months} month(s) Premium confirmed.\n"
                       f"📅 Expires: {new_expire.strftime('%Y-%m-%d')}\n\n"
                       f"Enjoy all Premium features! 🚗⚡")

        try:
            await context.bot.send_message(chat_id=uid, text=user_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Cannot notify user {uid}: {e}")

        await query.edit_message_caption(
            f"✅ <b>Confirmed #{payment_id}</b>\n"
            f"User: {uid} | {months} လ | {new_expire.strftime('%Y-%m-%d')} အထိ",
            parse_mode="HTML"
        )

    elif query.data.startswith("admin_reject_"):
        payment_id = int(query.data.replace("admin_reject_", ""))
        payment = db.get_pending_payment(payment_id)
        if not payment:
            await query.edit_message_caption("❌ Payment မတွေ့ပါ။")
            return

        uid = payment[1]
        db.update_payment_status(payment_id, "rejected")

        lang = db.get_language(uid)
        if lang == "MM":
            user_msg = ("❌ <b>Payment Rejected</b>\n\n"
                       "ငွေလွှဲ screenshot ကို အတည်မပြုနိုင်ပါ။\n"
                       "မှန်ကန်သော screenshot ထပ်ပို့ပေးပါ သို့မဟုတ် ဆက်သွယ်ပါ။")
        else:
            user_msg = ("❌ <b>Payment Rejected</b>\n\n"
                       "Could not verify your payment screenshot.\n"
                       "Please send the correct screenshot or contact support.")

        try:
            await context.bot.send_message(chat_id=uid, text=user_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Cannot notify user {uid}: {e}")

        await query.edit_message_caption(
            f"❌ <b>Rejected #{payment_id}</b>\nUser: {uid}",
            parse_mode="HTML"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin /stats command"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    total = db.get_total_users_count()
    premium = db.get_premium_users_count()
    pending = len(db.get_all_pending_payments())

    await update.message.reply_html(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{total}</b>\n"
        f"⭐ Premium Users: <b>{premium}</b>\n"
        f"💰 Pending Payments: <b>{pending}</b>\n"
        f"💵 Est. Revenue: MMK {premium * 5000:,}/month"
    )
