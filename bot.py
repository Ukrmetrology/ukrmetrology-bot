import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from dotenv import load_dotenv

from contracts import create_contract
from storage import Store

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
MANAGER_ID = int(os.getenv("MANAGER_ID", "512322547"))
MANAGER_IDS = {
    int(value.strip())
    for value in os.getenv("MANAGER_IDS", "").split(",")
    if value.strip().isdigit()
}
MANAGER_IDS.add(MANAGER_ID)
MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", str(MANAGER_ID)))
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+380 67 009 13 88")

if not TOKEN:
    raise RuntimeError("Заповніть BOT_TOKEN у файлі .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Store("data/bot.sqlite3")

SERVICES = [
    "Повірка водоміра",
    "Повірка теплолічильника",
    "Встановлення водоміра",
    "Встановлення теплолічильника",
    "Ремонт приладу обліку",
    "Консультація",
]
STREET_RE = re.compile(
    r"\b(вул(?:иця)?|просп(?:ект)?|пров(?:улок)?|пл(?:оща)?|бульв(?:ар)?|"
    r"шосе|дорога|набережна|узвіз|тупик|алея|мікрорайон|масив)\b",
    re.IGNORECASE,
)
HOUSE_NUMBER_RE = re.compile(
    r"\b(?:буд(?:инок)?\.?\s*)?(?:№\s*)?\d+[а-яa-z]?(?:/\d+)?\b",
    re.IGNORECASE,
)


class Intake(StatesGroup):
    name = State()
    phone = State()
    service = State()
    address = State()
    quantity = State()
    details = State()
    confirm = State()


def is_manager(user_id: int) -> bool:
    return user_id in MANAGER_IDS


def service_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=service, callback_data=f"svc:{i}")]
        for i, service in enumerate(SERVICES)
    ])


def confirmation_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Підтвердити", callback_data="confirm"),
        InlineKeyboardButton(text="Скасувати", callback_data="abort"),
    ]])


def manager_keyboard(app_id: int, include_approve: bool = True):
    rows = [[InlineKeyboardButton(
        text="Замінити DOCX договору", callback_data=f"replace:{app_id}"
    )]]
    if include_approve:
        rows.append([
            InlineKeyboardButton(text="Затвердити заявку", callback_data=f"approve:{app_id}"),
            InlineKeyboardButton(text="Відхилити", callback_data=f"reject:{app_id}"),
        ])
    else:
        rows.append([InlineKeyboardButton(text="Відхилити", callback_data=f"reject:{app_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def infer_device(service: str) -> str:
    if "водоміра" in service:
        return "Водомір"
    if "теплолічильника" in service:
        return "Теплолічильник"
    return "Не зазначено (уточнюється менеджером)"


def is_full_address(value: str) -> bool:
    address = " ".join(value.strip().split())
    parts = [part.strip() for part in address.split(",") if part.strip()]
    has_settlement = (
        bool(re.search(r"\b(м\.?|місто|с\.?|село|смт|селище)\b", address, re.IGNORECASE))
        or len(parts) >= 3
    )
    return (
        len(address) >= 12
        and len(parts) >= 2
        and has_settlement
        and bool(STREET_RE.search(address))
        and bool(HOUSE_NUMBER_RE.search(address))
    )


def local_date() -> str:
    return datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y")


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Подати заявку")]], resize_keyboard=True
    )
    await message.answer(
        "Вітаємо! Ви звернулися до ТОВ «УКРМЕТРОЛОГІЯ».\n\n"
        "Щоб оформити заявку, натисніть кнопку нижче.",
        reply_markup=keyboard,
    )


@dp.message(Command("myid"))
async def my_id(message: Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Оформлення заявки скасовано. Щоб почати знову, натисніть «Подати заявку».",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(F.text == "Подати заявку")
async def begin(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Intake.name)
    await message.answer(
        "Вкажіть ваше прізвище, ім’я та по батькові:",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Intake.name)
async def collect_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 4:
        return await message.answer("Будь ласка, введіть прізвище, ім’я та по батькові повністю.")
    await state.update_data(name=message.text.strip())
    await state.set_state(Intake.phone)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Надіслати номер телефону", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "Надішліть номер телефону кнопкою або введіть його вручну:",
        reply_markup=keyboard,
    )


@dp.message(Intake.phone)
async def collect_phone(message: Message, state: FSMContext):
    value = message.contact.phone_number if message.contact else (message.text or "").strip()
    if len(re.sub(r"\D", "", value)) < 9:
        return await message.answer("Перевірте номер телефону та введіть його ще раз.")
    await state.update_data(phone=value)
    await state.set_state(Intake.service)
    # Remove the contact-request keyboard before displaying service options.
    await message.answer("Дякуємо! Оберіть потрібну послугу:", reply_markup=ReplyKeyboardRemove())
    await message.answer("Оберіть послугу:", reply_markup=service_keyboard())


@dp.callback_query(F.data.startswith("svc:"))
async def collect_service(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != Intake.service.state:
        return await callback.answer()
    try:
        index = int(callback.data.split(":", 1)[1])
        service = SERVICES[index]
    except (ValueError, IndexError):
        return await callback.answer("Невідома послуга.", show_alert=True)

    device = infer_device(service)
    await state.update_data(service=service, device=device)
    await state.set_state(Intake.address)
    await callback.message.edit_text(f"Обрана послуга: {service}")
    await callback.message.answer(
        "Вкажіть повну адресу об’єкта: населений пункт, вулиця, номер будинку "
        "та квартиру (за наявності).\n\n"
        "Наприклад: м. Одеса, Південна дорога, буд. 57."
    )
    await callback.answer()


@dp.message(Intake.address)
async def collect_address(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_full_address(value):
        return await message.answer(
            "Адреса неповна. Вкажіть населений пункт, назву вулиці та номер будинку. "
            "За наявності додайте номер квартири.\n\n"
            "Приклад: м. Одеса, Південна дорога, буд. 57."
        )
    await state.update_data(address=" ".join(value.split()))
    await state.set_state(Intake.quantity)
    await message.answer("Скільки приладів потрібно обслужити або встановити? Вкажіть число:")


@dp.message(Intake.quantity)
async def collect_quantity(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit() or int(value) < 1:
        return await message.answer("Введіть ціле число, не менше 1.")
    await state.update_data(quantity=int(value))
    await state.set_state(Intake.details)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Немає")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "За можливістю вкажіть марку, модель та/або серійний номер приладу.\n"
        "Якщо цих даних немає, натисніть «Немає».",
        reply_markup=keyboard,
    )


@dp.message(Intake.details)
async def collect_details(message: Message, state: FSMContext):
    details = (message.text or "").strip()
    if not details or details.lower() in {"немає", "нема", "нет", "немає інформації"}:
        details = "Немає"
    await state.update_data(details=details)
    data = await state.get_data()
    await state.set_state(Intake.confirm)
    summary = (
        "Перевірте дані заявки:\n\n"
        f"ПІБ: {data['name']}\nТелефон: {data['phone']}\n"
        f"Послуга: {data['service']}\nТип приладу: {data['device']}\n"
        f"Адреса об’єкта: {data['address']}\nКількість: {data['quantity']}\n"
        f"Марка / модель / серійний номер: {details}"
    )
    await message.answer(summary, reply_markup=ReplyKeyboardRemove())
    await message.answer("Підтверджуєте правильність даних?", reply_markup=confirmation_keyboard())


@dp.callback_query(F.data == "abort")
async def abort(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Заявку скасовано. Щоб оформити нову, натисніть «Подати заявку».")
    await callback.answer()


@dp.callback_query(F.data == "confirm")
async def confirm(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != Intake.confirm.state:
        return await callback.answer()

    data = await state.get_data()
    data.update(
        user_id=callback.from_user.id,
        username=callback.from_user.username or "",
        created=datetime.now(ZoneInfo("Europe/Kyiv")).isoformat(timespec="seconds"),
    )
    app_id = db.create(data)
    contract_date = local_date()
    contract_no = f"{app_id:04d}/{contract_date}"
    data.update(id=app_id, contract_no=contract_no, contract_date=contract_date)
    db.update(app_id, data)

    contract_path = None
    contract_error = None
    try:
        contract_path = create_contract(data)
        db.set_contract(app_id, str(contract_path))
    except Exception as error:
        logger.exception("Contract generation failed for application %s", app_id)
        contract_error = str(error)

    await callback.message.edit_text("Заявку прийнято")
    manager_text = (
        f"НОВА ЗАЯВКА №{app_id}\nНомер договору: {contract_no}\n"
        f"Дата договору: {contract_date}\n\n"
        f"ПІБ: {data['name']}\nТелефон: {data['phone']}\n"
        f"Telegram: @{data['username'] or 'не вказано'}\n"
        f"Послуга: {data['service']}\nТип приладу: {data['device']}\n"
        f"Адреса об’єкта: {data['address']}\nКількість: {data['quantity']}\n"
        f"Марка / модель / серійний номер: {data['details']}\n\n"
        "Статус: очікує рішення менеджера."
    )
    try:
        await bot.send_message(
            MANAGER_CHAT_ID,
            manager_text + (f"\n\nПОМИЛКА ФОРМУВАННЯ ДОГОВОРУ: {contract_error}" if contract_error else ""),
            reply_markup=manager_keyboard(app_id, include_approve=bool(contract_path)),
        )
        if contract_path:
            await bot.send_document(
                MANAGER_CHAT_ID,
                FSInputFile(contract_path),
                caption=(
                    f"Заповнений проєкт договору №{contract_no}. "
                    "Перевірте документ, за потреби замініть DOCX, потім затвердіть."
                ),
            )
    except Exception:
        logger.exception("Could not send application %s to manager chat %s", app_id, MANAGER_CHAT_ID)
        await bot.send_message(
            callback.from_user.id,
            "Заявку прийнято, але сталася помилка передавання менеджеру. "
            "Будь ласка, зв’яжіться з компанією.",
        )

    await state.clear()
    await callback.answer()


@dp.callback_query(F.data.startswith("replace:"))
async def replace_contract(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        return await callback.answer(
            f"Недостатньо прав. Ваш Telegram ID: {callback.from_user.id}",
            show_alert=True,
        )
    app_id = int(callback.data.split(":", 1)[1])
    if not db.get(app_id):
        return await callback.answer("Заявку не знайдено.", show_alert=True)
    db.set_manager_mode(callback.from_user.id, app_id)
    try:
        await bot.send_message(
            callback.from_user.id,
            f"Надішліть у цей приватний чат новий DOCX-файл договору для заявки №{app_id}.",
        )
    except Exception:
        return await callback.answer(
            "Відкрийте приватний чат із ботом і натисніть /start, потім повторіть дію.",
            show_alert=True,
        )
    await callback.answer("Очікую DOCX у приватному чаті з ботом.")


@dp.message(F.document)
async def manager_document(message: Message):
    if not is_manager(message.from_user.id):
        return
    app_id = db.get_manager_mode(message.from_user.id)
    if not app_id:
        return
    filename = (message.document.file_name or "").lower()
    if not filename.endswith(".docx"):
        return await message.answer("Потрібен файл DOCX. Надішліть документ ще раз.")
    path = Path("data") / f"contract_{app_id}_manager.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    await bot.download(message.document, destination=path)
    db.set_contract(app_id, str(path))
    db.clear_manager_mode(message.from_user.id)
    await message.answer(
        f"Новий файл договору для заявки №{app_id} збережено. "
        "Тепер можна затвердити заявку кнопкою в повідомленні менеджера."
    )


@dp.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        return await callback.answer(
            f"Недостатньо прав. Ваш Telegram ID: {callback.from_user.id}",
            show_alert=True,
        )
    app_id = int(callback.data.split(":", 1)[1])
    data = db.get(app_id)
    if not data:
        return await callback.answer("Заявку не знайдено.", show_alert=True)
    contract = db.get_contract(app_id)
    if not contract or not Path(contract).exists():
        return await callback.answer("Файл договору відсутній. Завантажте DOCX заміни.", show_alert=True)

    # Prices and bank details are intentionally not a blocker at this stage.
    db.set_status(app_id, "approved")
    await bot.send_document(
        data["user_id"],
        FSInputFile(contract),
        caption="Ваш договір підготовлено. Будь ласка, перевірте документ.",
    )
    await callback.message.answer(f"Заявку №{app_id} затверджено. Договір надіслано клієнту.")
    await callback.answer("Договір надіслано клієнту.")


@dp.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        return await callback.answer(
            f"Недостатньо прав. Ваш Telegram ID: {callback.from_user.id}",
            show_alert=True,
        )
    app_id = int(callback.data.split(":", 1)[1])
    data = db.get(app_id)
    if not data:
        return await callback.answer("Заявку не знайдено.", show_alert=True)
    db.set_status(app_id, "rejected")
    await bot.send_message(
        data["user_id"],
        f"На жаль, вашу заявку відхилено. Якщо у вас є запитання, зв’яжіться з нами: {COMPANY_PHONE}.",
    )
    await callback.message.answer(f"Заявку №{app_id} відхилено. Клієнта повідомлено.")
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
