import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import asyncio

load_dotenv()

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardRemove, LabeledPrice, BotCommand
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Инициализация логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Получение токенов
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
PAYMENT_TOKEN = os.getenv('PAYMENT_TOKEN')
DEVELOPER_MODE = os.getenv('DEVELOPER_MODE', 'False').lower() == 'true'

if not API_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")
if not ADMIN_CHAT_ID:
    raise ValueError("Не указан ADMIN_CHAT_ID")
if not PAYMENT_TOKEN:
    logger.warning("PAYMENT_TOKEN не указан, оплата будет недоступна")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError:
    raise ValueError("ADMIN_CHAT_ID должен быть числовым идентификатором")

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Данные для заказа
FLAVORS_REGULAR = {
    "🍓 Шоколад+клубника": 2300,
    "🍌 Шокобанан": 2500,
    "☕️ Фисташка+малина": 2300,
    "🍒 Красный бархат+вишня": 2300,
    "🍰 Красный бархат+кремчиз": 2300,
    "🍯 Медовик+брусника": 2300,
    "🥛 Молочный бланш": 2300,
    "🥕 Морковный": 2300,
    "🍫 Шоколадный чизкейк": 2300,
    "🍵 Фисташ.чизкейк+вишня": 2300
}

FLAVORS_BENTO = {
    "🍓 Шоколад+клубника": 1200,
    "🍫 Сникерс": 1200,
    "☕️ Фисташка+малина": 1200,
    "🍒 Красный бархат+вишня": 1200
}

SIZES = {
    "1 кг": 1.0,
    "2 кг": 2.0,
    "3 кг": 3.0,
    "4 кг": 4.0,
    "5 кг": 5.0,
    "6 кг": 6.0,
    "7 кг": 7.0,
    "8 кг": 8.0,
    "9 кг": 9.0,
    "10 кг": 10.0,
    "11 кг": 11.0,
    "12 кг": 12.0,
    "13 кг": 13.0,
    "14 кг": 14.0,
    "15 кг": 15.0
}

CAKE_TYPES = {
    "🍰 Обычный торт": "regular",
    "🎂 Бенто-торт (400-450г)": "bento"
}

DECOR_OPTIONS_REGULAR = {
    "🎨 Рисунок цветной (от 500р)": 500,
    "✏️ Рисунок схематический (от 500р)": 500,
    "🖨 Печать на бумаге +370р": 370,
    "❌ Без оформления": 0
}

DECOR_OPTIONS_BENTO = {
    "🎨 Рисунок (от 300р)": 300,
    "🖨 Печать на бумаге +370р": 370,
    "❌ Без оформления": 0
}


class CakeOrder(StatesGroup):
    choosing_cake_type = State()
    choosing_flavor = State()
    choosing_size = State()
    choosing_cream_color = State()
    choosing_decor = State()
    choosing_cookies = State()
    cookies_count = State()
    cookies_photo = State()
    recipient_name = State()
    delivery_date = State()
    order_comment = State()
    photo_reference = State()
    user_contact = State()
    payment_method = State()
    payment_confirmation = State()


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Начать работу с ботом"),
        BotCommand(command="order", description="Сделать новый заказ"),
        BotCommand(command="help", description="Помощь по командам"),
        BotCommand(command="cancel", description="Отменить текущий заказ"),
        BotCommand(command="prices", description="Узнать расценки")
    ]

    if DEVELOPER_MODE:
        commands.extend([
            BotCommand(command="dev_paytest", description="Тест оплаты (dev)"),
            BotCommand(command="dev_skip", description="Пропустить оплату (dev)")
        ])

    await bot.set_my_commands(commands)


async def send_admin_notification(text: str, photo=None):
    try:
        if photo:
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML
            )
        else:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=text,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    disclaimer = (
        "⚠️ <b>Внимание!</b>\n\n"
        "Готовый торт может немного отличаться от ожидаемого изображения "
        "из-за особенностей ручной работы и натуральных ингредиентов.\n\n"
        "Для уточнения деталей с вами могут связаться сотрудники "
        "кофейни-кондитерской <b>«Сливки»</b>.\n\n"
        "Спасибо за понимание! ❤️"
    )

    builder = ReplyKeyboardBuilder()
    builder.button(text="/order")
    builder.button(text="/prices")
    builder.button(text="/help")
    builder.button(text="/cancel")

    if DEVELOPER_MODE:
        builder.button(text="/dev_paytest")
        builder.button(text="/dev_skip")

    builder.adjust(2)

    await message.answer(disclaimer, parse_mode=ParseMode.HTML)
    await message.answer(
        "🍰 Привет! Я СливкиБот - помогу оформить заказ торта!\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(Command("prices"))
async def cmd_prices(message: types.Message):
    regular_prices = "\n".join([f"{flavor} - {price}₽/кг" for flavor, price in FLAVORS_REGULAR.items()])
    bento_prices = "\n".join([f"{flavor} - {price}₽" for flavor, price in FLAVORS_BENTO.items()])

    prices_text = (
        "🎂 <b>Расценки на торты</b>\n\n"
        "<b>Обычные торты (цена за 1 кг):</b>\n"
        f"{regular_prices}\n\n"
        "<b>Бенто-торты (400-450г):</b>\n"
        f"{bento_prices}\n\n"
        "💡 Дополнительные опции (оформление, цвет крема и т.д.) оплачиваются отдельно.\n"
        "Окончательная стоимость будет рассчитана при оформлении заказа."
    )

    await message.answer(prices_text, parse_mode=ParseMode.HTML)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "❓ <b>Как сделать заказ:</b>\n\n"
        "1. Нажмите /order\n"
        "2. Выберите тип торта\n"
        "3. Выберите вкус\n"
        "4. Укажите параметры\n"
        "5. Введите данные для заказа\n\n"
        "<b>Основные команды:</b>\n"
        "/start - начать работу\n"
        "/order - новый заказ\n"
        "/prices - узнать расценки\n"
        "/help - помощь\n"
        "/cancel - отмена заказа"
    )

    if DEVELOPER_MODE:
        help_text += "\n\n<b>Команды разработчика:</b>\n"
        help_text += "/dev_paytest - тест оплаты\n"
        help_text += "/dev_skip - пропустить оплату"

    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(F.text == "Отменить заказ ❌")
@dp.message(Command("cancel"))
async def cancel_order(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Заказ отменен",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Command("order"))
async def start_order(message: types.Message, state: FSMContext):
    disclaimer = (
        "⚠️ <b>Перед оформлением заказа:</b>\n\n"
        "Мы уважаем труд наших кондитеров!\n\n"
        "На некоторые детали уходит больше сил и времени чем обычно.\n"
        "Поэтому в боте указывается примерная стоимость заказа.\n"
        "Она может отличаться, когда будете его забирать.\n\n"
        "Продолжая, вы соглашаетесь с этими условиями."
    )

    await message.answer(disclaimer, parse_mode=ParseMode.HTML)

    builder = ReplyKeyboardBuilder()
    for cake_type in CAKE_TYPES.keys():
        builder.button(text=cake_type)
    builder.button(text="Отменить заказ ❌")
    builder.adjust(1)

    await state.set_state(CakeOrder.choosing_cake_type)
    await message.answer(
        "🎂 Выберите тип торта:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.choosing_cake_type)
async def process_cake_type(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text not in CAKE_TYPES:
        await message.answer("Пожалуйста, выберите тип торта из предложенных")
        return

    cake_type = CAKE_TYPES[message.text]
    await state.update_data(cake_type=cake_type)
    flavors = FLAVORS_BENTO if cake_type == "bento" else FLAVORS_REGULAR

    builder = ReplyKeyboardBuilder()
    for flavor in flavors.keys():
        builder.button(text=flavor)
    builder.button(text="Отменить заказ ❌")
    builder.adjust(2)

    await state.set_state(CakeOrder.choosing_flavor)
    await message.answer(
        "🎂 Выберите вкус начинки:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.choosing_flavor)
async def process_flavor(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    data = await state.get_data()
    flavors = FLAVORS_BENTO if data.get('cake_type') == "bento" else FLAVORS_REGULAR

    if message.text not in flavors:
        await message.answer("Пожалуйста, выберите вкус из предложенных")
        return

    await state.update_data(flavor=message.text, price=flavors[message.text])

    if data.get('cake_type') == "bento":
        await state.set_state(CakeOrder.choosing_cream_color)
        await message.answer(
            "🎨 Укажите желаемый цвет крема (например: розовый, голубой, фисташковый).\n\n"
            "💡 Все цвета кроме белого добавляют +100₽ к стоимости.\n"
            "Напишите 'белый' если нужен стандартный белый крем.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        builder = ReplyKeyboardBuilder()
        for size in SIZES.keys():
            builder.button(text=size)
        builder.button(text="Отменить заказ ❌")
        builder.adjust(3)  # Теперь кнопки с размерами будут в 3 колонки
        await state.set_state(CakeOrder.choosing_size)
        await message.answer(
            "📏 Выберите размер:",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )


@dp.message(CakeOrder.choosing_cream_color)
async def process_cream_color(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    cream_color = message.text.strip().lower()
    cream_price = 100 if cream_color != "белый" else 0

    await state.update_data(
        cream_color=message.text,
        cream_price=cream_price
    )

    builder = ReplyKeyboardBuilder()
    for decor in DECOR_OPTIONS_BENTO.keys():
        builder.button(text=decor)
    builder.button(text="Отменить заказ ❌")
    builder.adjust(1)

    await state.set_state(CakeOrder.choosing_decor)
    await message.answer(
        "✨ Выберите вариант оформления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.choosing_size)
async def process_size(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text not in SIZES:
        await message.answer("Пожалуйста, выберите размер из предложенных")
        return

    data = await state.get_data()
    total_price = int(data['price'] * SIZES[message.text])
    await state.update_data(size=message.text, total_price=total_price)

    builder = ReplyKeyboardBuilder()
    for decor in DECOR_OPTIONS_REGULAR.keys():
        builder.button(text=decor)
    builder.button(text="Отменить заказ ❌")
    builder.adjust(2)

    await state.set_state(CakeOrder.choosing_decor)
    await message.answer(
        "✨ Выберите вариант оформления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.choosing_decor)
async def process_decor(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    data = await state.get_data()
    decor_options = DECOR_OPTIONS_BENTO if data.get('cake_type') == "bento" else DECOR_OPTIONS_REGULAR

    if message.text not in decor_options:
        await message.answer("Пожалуйста, выберите вариант оформления из предложенных")
        return

    await state.update_data(decor_option=message.text, decor_price=decor_options[message.text])

    # Переход к вопросу о пряниках
    await state.set_state(CakeOrder.choosing_cookies)
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да, добавить пряники")
    builder.button(text="Нет, продолжить без пряников")
    builder.button(text="Отменить заказ ❌")
    builder.adjust(1)
    await message.answer(
        "🍪 Хотите добавить пряники к заказу? (Цена от 160₽ за шт.)",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.choosing_cookies)
async def process_cookies_choice(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text == "Да, добавить пряники":
        await state.set_state(CakeOrder.cookies_count)
        await message.answer(
            "✏️ Укажите количество пряников:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif message.text == "Нет, продолжить без пряников":
        await state.update_data(cookies_count=0, cookies_price=0)
        await state.set_state(CakeOrder.recipient_name)
        await message.answer(
            "✏️ На чье имя оформляем заказ? (ФИО или как обращаться к получателю)",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer("Пожалуйста, выберите вариант из предложенных")


@dp.message(CakeOrder.cookies_count)
async def process_cookies_count(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    try:
        count = int(message.text)
        if count <= 0:
            await message.answer("Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число")
        return

    price_per_cookie = 160
    total_cookies_price = price_per_cookie * count

    await state.update_data(cookies_count=count, cookies_price=total_cookies_price)
    await state.set_state(CakeOrder.cookies_photo)
    await message.answer(
        "📸 Пришлите фото референса для пряников (если есть) или напишите 'пропустить'",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.cookies_photo, F.photo)
async def process_cookies_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(cookies_photo=photo_id)
    await state.set_state(CakeOrder.recipient_name)
    await message.answer(
        "✏️ На чье имя оформляем заказ? (ФИО или как обращаться к получателю)",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.cookies_photo)
async def skip_cookies_photo(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text.lower() != "пропустить":
        await message.answer("Пожалуйста, пришлите фото или напишите 'пропустить'")
        return

    await state.update_data(cookies_photo=None)
    await state.set_state(CakeOrder.recipient_name)
    await message.answer(
        "✏️ На чье имя оформляем заказ? (ФИО или как обращаться к получателю)",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.recipient_name)
async def process_recipient_name(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if not message.text or len(message.text) < 2:
        await message.answer("Пожалуйста, укажите имя получателя (минимум 2 символа)")
        return

    await state.update_data(recipient_name=message.text)
    await state.set_state(CakeOrder.delivery_date)
    await message.answer(
        "📅 На какую дату нужен торт? (Укажите в формате ДД.ММ.ГГГГ)\n\n"
        "Например: 15.08.2024",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.delivery_date)
async def process_delivery_date(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    try:
        delivery_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if delivery_date < datetime.now().date():
            await message.answer("Дата не может быть в прошлом. Укажите корректную дату")
            return
    except ValueError:
        await message.answer("Пожалуйста, укажите дату в формате ДД.ММ.ГГГГ")
        return

    await state.update_data(delivery_date=message.text)
    await state.set_state(CakeOrder.order_comment)
    await message.answer(
        "💬 Добавьте комментарий к заказу (если нужно):\n\n"
        "Если комментариев нет, напишите 'нет'",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.order_comment)
async def process_order_comment(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    comment = message.text if message.text.lower() != "нет" else "Без комментариев"
    await state.update_data(order_comment=comment)
    await state.set_state(CakeOrder.photo_reference)
    await message.answer(
        "📸 Пришлите фото референса (если есть) или напишите 'пропустить'",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CakeOrder.photo_reference, F.photo)
async def process_photo_reference(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_reference=photo_id)
    await ask_for_contact(message, state)


@dp.message(CakeOrder.photo_reference)
async def skip_photo_reference(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text.lower() != "пропустить":
        await message.answer("Пожалуйста, пришлите фото или напишите 'пропустить'")
        return

    await state.update_data(photo_reference=None)
    await ask_for_contact(message, state)


async def ask_for_contact(message: types.Message, state: FSMContext):
    await state.set_state(CakeOrder.user_contact)
    await message.answer(
        "📱 Укажите ваш номер телефона для связи:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="📱 Отправить контакт", request_contact=True)],
                [types.KeyboardButton(text="Отменить заказ ❌")]
            ],
            resize_keyboard=True
        )
    )


@dp.message(CakeOrder.user_contact, F.contact)
async def process_contact_from_button(message: types.Message, state: FSMContext):
    await process_contact(message, state, message.contact.phone_number)


@dp.message(CakeOrder.user_contact)
async def process_contact_from_text(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if not message.text or len(message.text) < 5:
        await message.answer("Пожалуйста, укажите корректный номер телефона")
        return
    await process_contact(message, state, message.text)


async def process_contact(message: types.Message, state: FSMContext, contact_info: str):
    await state.update_data(user_contact=contact_info)

    builder = ReplyKeyboardBuilder()
    builder.button(text="💳 Оплатить онлайн (≈50% предоплата)")

    if DEVELOPER_MODE:
        builder.button(text="🔧 Пропустить оплату (dev)")

    builder.button(text="Отменить заказ ❌")
    builder.adjust(1)

    await state.set_state(CakeOrder.payment_method)
    await message.answer(
        "💵 Для подтверждения заказа требуется внести ≈50% предоплаты:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(CakeOrder.payment_method)
async def process_payment(message: types.Message, state: FSMContext):
    if message.text == "Отменить заказ ❌":
        await cancel_order(message, state)
        return

    if message.text == "🔧 Пропустить оплату (dev)" and DEVELOPER_MODE:
        await state.update_data(payment_confirmation=True)
        await confirm_order(message, state)
        return

    if not PAYMENT_TOKEN:
        await message.answer("⚠️ Онлайн-оплата временно недоступна.")
        return

    data = await state.get_data()

    # Рассчитываем итоговую стоимость
    if data.get('cake_type') == "bento":
        base_price = FLAVORS_BENTO.get(data.get('flavor', ''), 0)
    else:
        size = data.get('size', '1 кг')
        size_value = float(size.split()[0])  # Изменили split()[1] на split()[0]
        base_price = FLAVORS_REGULAR.get(data.get('flavor', ''), 0) * size_value

    decor_price = data.get('decor_price', 0)
    cream_price = data.get('cream_price', 0)
    cookies_price = data.get('cookies_price', 0)

    total_price = int(base_price + decor_price + cream_price + cookies_price)
    prepayment_amount = int(total_price * 0.5)

    await state.update_data(total_price=total_price)

    prices = [LabeledPrice(label="Предоплата 50% за торт", amount=prepayment_amount * 100)]

    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Предоплата за торт {data.get('flavor', '')}",
            description=f"Размер: {data.get('size', '1 кг')}. Остаток оплачивается при получении.",
            payload="cake_prepayment",
            provider_token=PAYMENT_TOKEN,
            currency="RUB",
            prices=prices,
            need_name=True,
            need_phone_number=True
        )
    except Exception as e:
        logger.error(f"Ошибка при создании инвойса: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")


@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message, state: FSMContext):
    await state.update_data(payment_confirmation=True)
    await confirm_order(message, state)


@dp.message(Command("dev_paytest"))
async def dev_payment_test(message: types.Message, state: FSMContext):
    if not DEVELOPER_MODE:
        await message.answer("Эта команда доступна только в режиме разработчика")
        return

    builder = ReplyKeyboardBuilder()
    builder.button(text="100 руб")
    builder.button(text="500 руб")
    builder.button(text="1000 руб")
    builder.button(text="Отменить ❌")
    builder.adjust(2)

    await message.answer(
        "🔧 Тест оплаты. Выберите сумму:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message(F.text.endswith("руб") & F.from_user.id.in_({int(ADMIN_CHAT_ID)} if DEVELOPER_MODE else set()))
async def process_dev_payment_test(message: types.Message):
    try:
        amount = int(message.text.split()[0])
    except:
        await message.answer("Неверный формат суммы")
        return

    prices = [LabeledPrice(label="Тестовая оплата", amount=amount * 100)]

    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Тест оплаты",
            description=f"Тестовая оплата на сумму {amount} руб",
            payload="dev_test_payment",
            provider_token=PAYMENT_TOKEN,
            currency="RUB",
            prices=prices
        )
    except Exception as e:
        logger.error(f"Ошибка при тесте оплаты: {e}")
        await message.answer("Ошибка при создании платежа")


@dp.message(Command("dev_skip"))
async def dev_skip_payment(message: types.Message, state: FSMContext):
    if not DEVELOPER_MODE:
        await message.answer("Эта команда доступна только в режиме разработчика")
        return

    current_state = await state.get_state()
    if current_state == CakeOrder.payment_method:
        await state.update_data(payment_confirmation=True)
        await confirm_order(message, state)
    else:
        await message.answer("Эта команда работает только на этапе оплаты")


async def confirm_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"

    # Рассчитываем итоговую стоимость
    if data.get('cake_type') == "bento":
        base_price = FLAVORS_BENTO.get(data.get('flavor', ''), 0)
    else:
        size = data.get('size', '1 кг')
        size_value = float(size.split()[0])  # Изменили split()[1] на split()[0]
        base_price = FLAVORS_REGULAR.get(data.get('flavor', ''), 0) * size_value

    decor_price = data.get('decor_price', 0)
    cream_price = data.get('cream_price', 0)
    cookies_price = data.get('cookies_price', 0)


    total_price = int(base_price + decor_price + cream_price + cookies_price)

    order_text = (
        f"🎂 <b>НОВЫЙ ЗАКАЗ {'БЕНТО-' if data.get('cake_type') == 'bento' else ''}ТОРТА</b>\n\n"
        f"👤 Клиент: {username}\n"
        f"📱 Тел: {data.get('user_contact', 'не указан')}\n"
        f"💳 Способ оплаты: {'Предоплата 50%' if data.get('payment_confirmation') else 'Не оплачено'}\n\n"
    )

    if data.get('cake_type') == "bento":
        order_text += (
            f"🎂 Тип: Бенто-торт (400-450г)\n"
            f"🍰 Вкус: {data.get('flavor', 'не выбран')}\n"
            f"🎨 Цвет крема: {data.get('cream_color', 'не выбран')} "
            f"{'(+100₽)' if data.get('cream_price', 0) > 0 else ''}\n"
        )
    else:
        order_text += (
            f"🎂 Тип: Обычный торт\n"
            f"🍰 Вкус: {data.get('flavor', 'не выбран')}\n"
            f"📏 Размер: {data.get('size', 'не выбран')}\n"
        )

    order_text += (
        f"✨ Оформление: {data.get('decor_option', 'не выбрано')}\n"
    )

    if data.get('cookies_count', 0) > 0:
        order_text += f"🍪 Пряники: {data.get('cookies_count')} шт. ({data.get('cookies_price', 0)}₽)\n"

    order_text += (
        f"👑 Получатель: {data.get('recipient_name', 'не указано')}\n"
        f"📅 Дата: {data.get('delivery_date', 'не указана')}\n"
        f"💵 Сумма: {total_price}₽\n\n"
        f"📝 Комментарий:\n{data.get('order_comment', 'нет')}\n\n"
        f"#заказ #{'бенто' if data.get('cake_type') == 'bento' else 'торт'}"
    )

    # Отправляем фото референса торта, если есть
    photo_id = data.get('photo_reference')
    if photo_id:
        await send_admin_notification(order_text, photo=photo_id)
    else:
        await send_admin_notification(order_text)

    # Отправляем фото референса пряников отдельно, если есть
    cookies_photo_id = data.get('cookies_photo')
    if cookies_photo_id:
        await send_admin_notification("📸 Референс для пряников:", photo=cookies_photo_id)

    confirmation_message = (
        "✅ <b>Ваш заказ принят!</b> Вот детали:\n\n"
        f"🎂 Тип: {'Бенто-торт' if data.get('cake_type') == 'bento' else 'Обычный торт'}\n"
        f"👑 Получатель: {data.get('recipient_name', 'не указано')}\n"
        f"📅 Дата: {data.get('delivery_date', 'не указана')}\n"
        f"🍰 Вкус: {data.get('flavor', 'не выбран')}\n"
    )

    if data.get('cake_type') != "bento":
        confirmation_message += f"📏 Размер: {data.get('size', 'не выбран')}\n"

    if data.get('cake_type') == "bento":
        confirmation_message += f"🎨 Цвет крема: {data.get('cream_color', 'не выбран')}\n"

    confirmation_message += (
        f"✨ Оформление: {data.get('decor_option', 'не выбрано')}\n"
    )

    if data.get('cookies_count', 0) > 0:
        confirmation_message += f"🍪 Пряники: {data.get('cookies_count')} шт.\n"

    confirmation_message += (
        f"💵 Сумма:≈ {total_price}₽\n\n"
    )

    if data.get('payment_confirmation'):
        confirmation_message += "✅ Оплата получена\n\n"
    else:
        confirmation_message += "⚠️ Оплата не произведена\n\n"

    confirmation_message += (
        "Наш кондитер свяжется с вами для уточнения деталей.\n"
        "Спасибо за заказ! ❤️"
    )

    await message.answer(confirmation_message, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    await state.clear()


async def main():
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())