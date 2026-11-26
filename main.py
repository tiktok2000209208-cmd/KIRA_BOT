import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# =============== SETTINGS ===============
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_NAME = os.getenv("DB_PATH", "kira_orders.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============== DATABASE ===============
@contextmanager
def db():
    con = sqlite3.connect(DB_NAME, timeout=30)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                phone TEXT DEFAULT '',
                lang TEXT DEFAULT 'ru'
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                username TEXT,
                phone TEXT,
                pay_country TEXT,
                connection_country TEXT,
                payment_method TEXT,
                price TEXT,
                status TEXT DEFAULT 'Новый',
                created TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                review TEXT,
                created TEXT
            )
        """)


def save_user(user):
    with db() as con:
        con.execute("""
            INSERT INTO users (user_id, name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name,
                username=excluded.username
        """, (user.id, user.full_name, user.username))


def get_lang(user_id):
    with db() as con:
        row = con.execute(
            "SELECT lang FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    return row[0] if row else "ru"


def set_language(user_id, lang):
    with db() as con:
        con.execute("""
            INSERT INTO users (user_id, lang)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang
        """, (user_id, lang))


# =============== TEXTS ===============
TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать в KIRA-BOT 4.0!",
        "menu": "Выберите действие:",
        "order": "🛒 Новый заказ",
        "history": "📦 Мои заказы",
        "review": "⭐ Оставить отзыв",
        "language": "🌐 Язык",
        "country": "Выберите страну оплаты:",
        "connection": "Выберите страну подключения:",
        "method": "Выберите способ оплаты:",
        "contact": "Отправьте свой номер телефона или нажмите «Пропустить».",
        "skip": "Пропустить",
        "confirm": "Подтвердить",
        "cancel": "Отменить",
        "accepted": "✅ Заказ принят! Ожидайте ответа администратора.",
        "cancelled": "Заказ отменён.",
        "review_text": "Напишите свой отзыв:",
        "review_done": "Спасибо за отзыв! ⭐",
        "no_orders": "У вас пока нет заказов.",
        "unknown": "Используйте кнопки меню или /start.",
        "no_phone": "Не указан"
    },
    "ky": {
        "welcome": "👋 KIRA-BOT 4.0 ботуна кош келиңиз!",
        "menu": "Керектүү бөлүмдү тандаңыз:",
        "order": "🛒 Жаңы буйрутма",
        "history": "📦 Менин буйрутмаларым",
        "review": "⭐ Пикир калтыруу",
        "language": "🌐 Тил",
        "country": "Төлөм өлкөсүн тандаңыз:",
        "connection": "Туташуу өлкөсүн тандаңыз:",
        "method": "Төлөм ыкмасын тандаңыз:",
        "contact": "Телефон номериңизди жөнөтүңүз же өткөрүп жибериңиз.",
        "skip": "Өткөрүп жиберүү",
        "confirm": "Ырастоо",
        "cancel": "Жокко чыгаруу",
        "accepted": "✅ Буйрутма кабыл алынды!",
        "cancelled": "Буйрутма жокко чыгарылды.",
        "review_text": "Пикириңизди жазыңыз:",
        "review_done": "Пикириңиз үчүн рахмат! ⭐",
        "no_orders": "Сизде азырынча буйрутмалар жок.",
        "unknown": "/start командасын же менюну колдонуңуз.",
        "no_phone": "Көрсөтүлгөн эмес"
    },
    "en": {
        "welcome": "👋 Welcome to KIRA-BOT 4.0!",
        "menu": "Choose an option:",
        "order": "🛒 New order",
        "history": "📦 My orders",
        "review": "⭐ Leave a review",
        "language": "🌐 Language",
        "country": "Choose payment country:",
        "connection": "Choose connection country:",
        "method": "Choose payment method:",
        "contact": "Share your phone number or skip.",
        "skip": "Skip",
        "confirm": "Confirm",
        "cancel": "Cancel",
        "accepted": "✅ Order received!",
        "cancelled": "Order cancelled.",
        "review_text": "Write your review:",
        "review_done": "Thank you for your review! ⭐",
        "no_orders": "You have no orders yet.",
        "unknown": "Use the menu buttons or /start.",
        "no_phone": "Not provided"
    }
}


def tr(lang, key):
    return TEXTS.get(lang, TEXTS["ru"]).get(
        key, TEXTS["ru"].get(key, key)
    )


# =============== COUNTRIES / PRICES ===============
PRICES = {
    "🇰🇬 Кыргызстан": "199 сом",
    "🇰🇿 Казахстан": "999 тенге",
    "🇷🇺 Россия": "299 рублей",
}
CONNECTIONS = ["🇨🇱 Чили", "🇧🇷 Бразилия", "🇨🇴 Колумбия", "🇹🇭 Таиланд"]
PAYMENTS = {
    "🇰🇬 Кыргызстан": ["MBank", "O!Bank", "Элкарт", "Visa", "Mastercard"],
    "🇰🇿 Казахстан": ["Kaspi Gold", "Halyk Bank", "ForteBank"],
    "🇷🇺 Россия": ["Сбербанк", "Т-Банк", "ВТБ", "Мир"],
}
STATUS_NAMES = {
    "processing": "🔵 В обработке",
    "done": "🟢 Выполнен",
    "cancelled": "🔴 Отменён",
}


# =============== KEYBOARDS ===============
def menu_keyboard(lang):
    return ReplyKeyboardMarkup([
        [tr(lang, "order")],
        [tr(lang, "history"), tr(lang, "review")],
        [tr(lang, "language")]
    ], resize_keyboard=True)


def language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton("🇰🇬 Кыргызча", callback_data="lang:ky")
        ],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Все заказы", callback_data="admin:orders")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")]
    ])


def admin_order_keyboard(order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🔵 В обработке",
            callback_data=f"status:{order_id}:processing"
        )],
        [
            InlineKeyboardButton(
                "🟢 Выполнен", callback_data=f"status:{order_id}:done"
            ),
            InlineKeyboardButton(
                "🔴 Отменён", callback_data=f"status:{order_id}:cancelled"
            )
        ],
        [InlineKeyboardButton(
            "✉️ Ответить клиенту", callback_data=f"reply:{order_id}"
        )]
    ])


def country_keyboard():
    return ReplyKeyboardMarkup([[x] for x in PRICES], resize_keyboard=True)


def connection_keyboard():
    return ReplyKeyboardMarkup([[x] for x in CONNECTIONS], resize_keyboard=True)


def method_keyboard(country):
    return ReplyKeyboardMarkup(
        [[x] for x in PAYMENTS.get(country, [])], resize_keyboard=True
    )


def contact_keyboard(lang):
    return ReplyKeyboardMarkup([
        [KeyboardButton("📱 Отправить номер телефона", request_contact=True)],
        [tr(lang, "skip")]
    ], resize_keyboard=True)


def confirm_keyboard(lang):
    return ReplyKeyboardMarkup([
        [tr(lang, "confirm"), tr(lang, "cancel")]
    ], resize_keyboard=True)


# =============== START / LANGUAGE ===============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    context.user_data.clear()
    await update.message.reply_text(
        "🌐 Выберите язык / Тилди тандаңыз / Choose language:",
        reply_markup=language_keyboard()
    )


async def language_callback(update, context):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    if lang not in TEXTS:
        return
    set_language(query.from_user.id, lang)
    await query.edit_message_text(tr(lang, "welcome"))
    await query.message.reply_text(
        tr(lang, "menu"), reply_markup=menu_keyboard(lang)
    )


# =============== ORDERS ===============
async def begin_order(message, context, lang):
    context.user_data.clear()
    context.user_data["step"] = "pay_country"
    await message.reply_text(
        tr(lang, "country"), reply_markup=country_keyboard()
    )


async def save_order(user, context):
    data = context.user_data
    phone = data.get("phone", "")
    username = user.username or "Нет username"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db() as con:
        cur = con.execute("""
            INSERT INTO orders (
                user_id, name, username, phone, pay_country,
                connection_country, payment_method, price, status, created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id, user.full_name, username, phone,
            data["pay_country"], data["connection"], data["method"],
            data["price"], "Новый", now
        ))
        order_id = cur.lastrowid
        con.execute(
            "UPDATE users SET phone=? WHERE user_id=?", (phone, user.id)
        )
    return order_id, now


async def show_confirmation(message, context, lang):
    data = context.user_data
    order_text = (
        f"📋 Ваш заказ:\n\n"
        f"🌍 Оплата: {data['pay_country']}\n"
        f"📍 Подключение: {data['connection']}\n"
        f"💳 Способ: {data['method']}\n"
        f"💰 Цена: {data['price']}\n"
        f"📱 Телефон: {data.get('phone') or tr(lang, 'no_phone')}\n\n"
        f"Проверьте данные и подтвердите заказ."
    )
    context.user_data["step"] = "confirm"
    await message.reply_text(
        order_text, reply_markup=confirm_keyboard(lang)
    )


async def show_history(message, user_id, lang):
    with db() as con:
        rows = con.execute("""
            SELECT id, pay_country, connection_country, payment_method,
                   price, status, created
            FROM orders WHERE user_id=?
            ORDER BY id DESC LIMIT 15
        """, (user_id,)).fetchall()
    if not rows:
        await message.reply_text(tr(lang, "no_orders"))
        return
    for row in rows:
        await message.reply_text(
            f"📦 Заказ №{row[0]}\n"
            f"🌍 Оплата: {row[1]}\n"
            f"📍 Подключение: {row[2]}\n"
            f"💳 Способ: {row[3]}\n"
            f"💰 Цена: {row[4]}\n"
            f"📌 Статус: {row[5]}\n"
            f"📅 Дата: {row[6]}"
        )


# =============== ADMIN ===============
async def admin_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text(
        "🔐 Панель администратора", reply_markup=admin_keyboard()
    )


async def admin_callback(update, context):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа!", show_alert=True)
        return
    await query.answer()

    if query.data == "admin:orders":
        with db() as con:
            rows = con.execute("""
                SELECT id, user_id, name, username, phone, pay_country,
                       connection_country, payment_method, price, status, created
                FROM orders ORDER BY id DESC LIMIT 15
            """).fetchall()
        if not rows:
            await query.message.reply_text("Заказов пока нет.")
            return
        for row in rows:
            order_text = (
                f"🆕 ЗАКАЗ №{row[0]}\n\n"
                f"👤 Имя: {row[2]}\n"
                f"🆔 ID: {row[1]}\n"
                f"🔗 Username: @{row[3]}\n"
                f"📱 Телефон: {row[4] or 'Не указан'}\n"
                f"🌍 Оплата: {row[5]}\n"
                f"📍 Подключение: {row[6]}\n"
                f"💳 Метод: {row[7]}\n"
                f"💰 Цена: {row[8]}\n"
                f"📌 Статус: {row[9]}\n"
                f"📅 Дата: {row[10]}"
            )
            await query.message.reply_text(
                order_text, reply_markup=admin_order_keyboard(row[0])
            )

    elif query.data == "admin:stats":
        with db() as con:
            total = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            new_count = con.execute(
                "SELECT COUNT(*) FROM orders WHERE status='Новый'"
            ).fetchone()[0]
            processing = con.execute(
                "SELECT COUNT(*) FROM orders WHERE status=?",
                (STATUS_NAMES["processing"],)
            ).fetchone()[0]
            done = con.execute(
                "SELECT COUNT(*) FROM orders WHERE status=?",
                (STATUS_NAMES["done"],)
            ).fetchone()[0]
            cancelled = con.execute(
                "SELECT COUNT(*) FROM orders WHERE status=?",
                (STATUS_NAMES["cancelled"],)
            ).fetchone()[0]
            users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            reviews = con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        await query.message.reply_text(
            "📊 СТАТИСТИКА KIRA-BOT\n\n"
            f"👥 Пользователей: {users}\n"
            f"📦 Всего заказов: {total}\n"
            f"🆕 Новых: {new_count}\n"
            f"🔵 В обработке: {processing}\n"
            f"🟢 Выполненных: {done}\n"
            f"🔴 Отменённых: {cancelled}\n"
            f"⭐ Отзывов: {reviews}"
        )


async def status_callback(update, context):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа!", show_alert=True)
        return
    await query.answer()
    try:
        _, order_id, status = query.data.split(":")
        order_id = int(order_id)
        if status not in STATUS_NAMES:
            return
        new_status = STATUS_NAMES[status]
        with db() as con:
            row = con.execute(
                "SELECT user_id FROM orders WHERE id=?", (order_id,)
            ).fetchone()
            if not row:
                await query.message.reply_text("Заказ не найден.")
                return
            con.execute(
                "UPDATE orders SET status=? WHERE id=?",
                (new_status, order_id)
            )
        await query.edit_message_reply_markup(
            reply_markup=admin_order_keyboard(order_id)
        )
        try:
            await context.bot.send_message(
                chat_id=row[0],
                text=f"📦 Статус вашего заказа №{order_id} изменён:\n{new_status}"
            )
        except Exception:
            logger.exception("Не удалось уведомить клиента")
        await query.message.reply_text(
            f"✅ Статус заказа №{order_id}: {new_status}"
        )
    except Exception:
        logger.exception("Ошибка изменения статуса")
        await query.message.reply_text("❌ Не удалось изменить статус.")


async def reply_callback(update, context):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа!", show_alert=True)
        return
    await query.answer()
    try:
        order_id = int(query.data.split(":")[1])
        with db() as con:
            row = con.execute(
                "SELECT user_id FROM orders WHERE id=?", (order_id,)
            ).fetchone()
        if not row:
            await query.message.reply_text("Заказ не найден.")
            return
        context.user_data["reply_order"] = order_id
        await query.message.reply_text(
            f"✉️ Ответ на заказ №{order_id}\nНапишите сообщение клиенту:"
        )
    except Exception:
        logger.exception("Ошибка подготовки ответа")
        await query.message.reply_text("Ошибка. Попробуйте ещё раз.")


# =============== MESSAGE HANDLER ===============
async def handle_message(update, context):
    message = update.message
    user = update.effective_user
    if not message or not user:
        return

    text = message.text or ""
    lang = get_lang(user.id)
    save_user(user)

    # Admin reply to customer
    if user.id == ADMIN_ID and context.user_data.get("reply_order"):
        order_id = context.user_data.pop("reply_order")
        with db() as con:
            row = con.execute(
                "SELECT user_id FROM orders WHERE id=?", (order_id,)
            ).fetchone()
        if not row:
            await message.reply_text("Заказ не найден.")
            return
        try:
            await context.bot.send_message(
                chat_id=row[0],
                text="📩 Сообщение администратора:\n\n" + text
            )
            await message.reply_text("✅ Сообщение отправлено клиенту.")
        except Exception:
            logger.exception("Ошибка ответа клиенту")
            await message.reply_text("❌ Не удалось отправить сообщение.")
        return

    if text == tr(lang, "order"):
        await begin_order(message, context, lang)
        return
    if text == tr(lang, "history"):
        await show_history(message, user.id, lang)
        return
    if text == tr(lang, "review"):
        context.user_data.clear()
        context.user_data["step"] = "review"
        await message.reply_text(tr(lang, "review_text"))
        return
    if text == tr(lang, "language"):
        await start(update, context)
        return

    step = context.user_data.get("step")

    if step == "pay_country":
        if text not in PRICES:
            await message.reply_text(tr(lang, "country"))
            return
        context.user_data["pay_country"] = text
        context.user_data["price"] = PRICES[text]
        context.user_data["step"] = "connection"
        await message.reply_text(
            tr(lang, "connection"), reply_markup=connection_keyboard()
        )
        return

    if step == "connection":
        if text not in CONNECTIONS:
            await message.reply_text(tr(lang, "connection"))
            return
        context.user_data["connection"] = text
        context.user_data["step"] = "method"
        country = context.user_data["pay_country"]
        await message.reply_text(
            tr(lang, "method"), reply_markup=method_keyboard(country)
        )
        return

    if step == "method":
        country = context.user_data.get("pay_country")
        if text not in PAYMENTS.get(country, []):
            await message.reply_text(
                tr(lang, "method"), reply_markup=method_keyboard(country)
            )
            return
        context.user_data["method"] = text
        context.user_data["step"] = "phone"
        await message.reply_text(
            tr(lang, "contact"), reply_markup=contact_keyboard(lang)
        )
        return

    if step == "phone":
        if message.contact:
            if message.contact.user_id not in (None, user.id):
                await message.reply_text(
                    "Отправьте, пожалуйста, свой номер телефона.",
                    reply_markup=contact_keyboard(lang)
                )
                return
            context.user_data["phone"] = message.contact.phone_number
        elif text == tr(lang, "skip"):
            context.user_data["phone"] = ""
        else:
            await message.reply_text(
                tr(lang, "contact"), reply_markup=contact_keyboard(lang)
            )
            return
        await show_confirmation(message, context, lang)
        return

    if step == "confirm":
        if text == tr(lang, "cancel"):
            context.user_data.clear()
            await message.reply_text(
                tr(lang, "cancelled"), reply_markup=menu_keyboard(lang)
            )
            return
        if text == tr(lang, "confirm"):
            try:
                order_id, created = await save_order(user, context)
                data = context.user_data
                admin_text = (
                    f"🆕 НОВЫЙ ЗАКАЗ №{order_id}\n\n"
                    f"👤 Имя: {user.full_name}\n"
                    f"🆔 ID: {user.id}\n"
                    f"🔗 Username: @{user.username or 'Нет username'}\n"
                    f"📱 Телефон: {data.get('phone') or 'Не указан'}\n"
                    f"🌍 Оплата: {data['pay_country']}\n"
                    f"📍 Подключение: {data['connection']}\n"
                    f"💳 Метод: {data['method']}\n"
                    f"💰 Цена: {data['price']}\n"
                    f"📅 Дата: {created}"
                )
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=admin_text,
                        reply_markup=admin_order_keyboard(order_id)
                    )
                except Exception:
                    logger.exception("Не удалось отправить заказ админу")
                context.user_data.clear()
                await message.reply_text(
                    tr(lang, "accepted"), reply_markup=menu_keyboard(lang)
                )
            except Exception:
                logger.exception("Ошибка сохранения заказа")
                await message.reply_text(
                    "❌ Не удалось сохранить заказ. Попробуйте ещё раз."
                )
            return
        await message.reply_text("Нажмите кнопку подтверждения или отмены.")
        return

    if step == "review":
        if not text.strip():
            await message.reply_text(tr(lang, "review_text"))
            return
        with db() as con:
            con.execute("""
                INSERT INTO reviews (user_id, review, created)
                VALUES (?, ?, ?)
            """, (
                user.id, text.strip(),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        context.user_data.clear()
        await message.reply_text(
            tr(lang, "review_done"), reply_markup=menu_keyboard(lang)
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⭐ НОВЫЙ ОТЗЫВ\n"
                    f"👤 {user.full_name}\n"
                    f"🆔 {user.id}\n\n{text}"
                )
            )
        except Exception:
            logger.exception("Не удалось отправить отзыв админу")
        return

    await message.reply_text(
        tr(lang, "unknown"), reply_markup=menu_keyboard(lang)
    )


# =============== ERRORS / RUN ===============
async def error_handler(update, context):
    logger.error(
        "Ошибка при обработке обновления",
        exc_info=context.error
    )


def main():
    if not TOKEN:
        print("ОШИБКА: задайте переменную BOT_TOKEN в настройках Railway.")
        return
    if ADMIN_ID <= 0:
        print("ОШИБКА: задайте ADMIN_ID в настройках Railway.")
        return

    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(status_callback, pattern=r"^status:"))
    app.add_handler(CallbackQueryHandler(reply_callback, pattern=r"^reply:"))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.CONTACT, handle_message
    ))
    app.add_error_handler(error_handler)

    print("KIRA-BOT 4.0 запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
