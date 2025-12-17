import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv
import db

# ================= ENV =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "fleet.db")

# ================= ROOT ADMINS =================
ADMIN_IDS = {5643220428}

# ================= FSM =================
class AddCarStates(StatesGroup):
    vin = State()
    mileage = State()
    year = State()
    owner_company = State()
    model = State()
    plate = State()
    fuel_type = State()


class NewServiceStates(StatesGroup):
    car_identifier = State()
    description = State()
    desired_at = State()


class AddRoleStates(StatesGroup):
    tg_id = State()


class FinishServiceStates(StatesGroup):
    service_id = State()
    mileage = State()
    cost = State()
    comment = State()


# ================= BUTTONS =================
BTN_CARS = "🚗 Автомобили"
BTN_SERVICES = "🔧 Сервисы"
BTN_ADMIN = "⚙️ Админка"
BTN_MY_SERVICES = "🛠 Мои сервисы"

# ================= HELPERS =================
async def ensure_user(tg_id: int, full_name: str):
    db.add_user(DB_PATH, tg_id, full_name)
    if tg_id in ADMIN_IDS:
        db.set_user_role(DB_PATH, tg_id, "admin")


def get_role(tg_id: int) -> str:
    return db.get_user_role(DB_PATH, tg_id) or "user"


def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS or get_role(tg_id) == "admin"


# ================= KEYBOARDS =================
def main_kb(role: str):
    if role == "admin":
        rows = [
            [KeyboardButton(text=BTN_CARS), KeyboardButton(text=BTN_SERVICES)],
            [KeyboardButton(text=BTN_ADMIN)],
        ]
    elif role == "mechanic":
        rows = [
            [KeyboardButton(text=BTN_SERVICES)],
            [KeyboardButton(text=BTN_MY_SERVICES)],
        ]
    else:
        rows = [[KeyboardButton(text=BTN_SERVICES)]]

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cars_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить авто", callback_data="car:add")],
        [InlineKeyboardButton(text="📄 Список авто", callback_data="car:list")],
    ])


def services_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Новый сервис", callback_data="service:new")],
        [InlineKeyboardButton(text="⏳ Ожидают сервиса", callback_data="service:pending")],
        [InlineKeyboardButton(text="📋 История", callback_data="service:history")],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin:add_admin")],
        [InlineKeyboardButton(text="➕ Добавить механика", callback_data="admin:add_mechanic")],
    ])


def mechanics_kb(mechanics, service_id):
    rows = []
    for m in mechanics:
        rows.append([
            InlineKeyboardButton(
                text=m["full_name"] or str(m["tg_id"]),
                callback_data=f"service:assign:{service_id}:{m['tg_id']}"
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="Без механика",
            callback_data=f"service:assign:{service_id}:none"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= BOT =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    await ensure_user(message.from_user.id, message.from_user.full_name or "")
    role = get_role(message.from_user.id)
    await message.answer(
        f"Здравствуйте, {message.from_user.full_name}\nРоль: {role}",
        reply_markup=main_kb(role)
    )

# ================= MAIN MENUS =================
@dp.message(F.text == BTN_CARS)
async def cars_menu(message: Message):
    await message.answer("🚗 Автомобили:", reply_markup=cars_kb())


@dp.message(F.text == BTN_SERVICES)
async def services_menu(message: Message):
    await message.answer("🔧 Сервисы:", reply_markup=services_kb())


@dp.message(F.text == BTN_ADMIN)
async def admin_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚙️ Админка:", reply_markup=admin_kb())

# ================= ADMIN =================
@dp.callback_query(F.data.startswith("admin:add"))
async def add_role(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    role = "admin" if "admin" in call.data else "mechanic"
    await state.set_state(AddRoleStates.tg_id)
    await state.update_data(role=role)
    await call.message.answer(f"Введите TG ID для роли {role}")


@dp.message(AddRoleStates.tg_id)
async def save_role(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        tg_id = int(message.text)
    except ValueError:
        await message.answer("Некорректный TG ID")
        return
    db.add_user(DB_PATH, tg_id, "")
    db.set_user_role(DB_PATH, tg_id, data["role"])
    await state.clear()
    await message.answer("Готово")

# ================= CARS =================
@dp.callback_query(F.data == "car:add")
async def add_car_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AddCarStates.vin)
    await call.message.answer("VIN:")


@dp.message(AddCarStates.vin)
async def add_car_vin(message: Message, state: FSMContext):
    await state.update_data(vin=message.text.upper())
    await state.set_state(AddCarStates.mileage)
    await message.answer("Пробег:")


@dp.message(AddCarStates.mileage)
async def add_car_mileage(message: Message, state: FSMContext):
    await state.update_data(mileage=int(message.text))
    await state.set_state(AddCarStates.year)
    await message.answer("Год:")


@dp.message(AddCarStates.year)
async def add_car_year(message: Message, state: FSMContext):
    await state.update_data(year=int(message.text))
    await state.set_state(AddCarStates.owner_company)
    await message.answer("Владелец:")


@dp.message(AddCarStates.owner_company)
async def add_car_owner(message: Message, state: FSMContext):
    await state.update_data(owner_company=message.text)
    await state.set_state(AddCarStates.model)
    await message.answer("Модель:")


@dp.message(AddCarStates.model)
async def add_car_model(message: Message, state: FSMContext):
    await state.update_data(model=message.text)
    await state.set_state(AddCarStates.plate)
    await message.answer("Номер:")


@dp.message(AddCarStates.plate)
async def add_car_plate(message: Message, state: FSMContext):
    await state.update_data(plate=message.text.upper())
    await state.set_state(AddCarStates.fuel_type)
    await message.answer("Топливо:")


@dp.message(AddCarStates.fuel_type)
async def add_car_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    car_id = db.add_car(DB_PATH, **data, fuel_type=message.text)
    await state.clear()
    await message.answer(f"Авто добавлено. ID {car_id}")

# ================= SERVICES =================
@dp.callback_query(F.data == "service:new")
async def new_service(call: CallbackQuery, state: FSMContext):
    await state.set_state(NewServiceStates.car_identifier)
    await call.message.answer("VIN / номер / ID авто:")


@dp.message(NewServiceStates.car_identifier)
async def service_car(message: Message, state: FSMContext):
    car = db.find_car_by_identifier(DB_PATH, message.text)
    if not car:
        await message.answer("Авто не найдено")
        return
    await state.update_data(car_id=car["id"])
    await state.set_state(NewServiceStates.description)
    await message.answer("Описание работ:")


@dp.message(NewServiceStates.description)
async def service_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(NewServiceStates.desired_at)
    await message.answer("Дата / время:")


@dp.message(NewServiceStates.desired_at)
async def service_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = db.create_service(
        DB_PATH,
        car_id=data["car_id"],
        creator_tg_id=message.from_user.id,
        creator_role=get_role(message.from_user.id),
        description=data["description"],
        desired_at=message.text
    )
    await state.clear()

    if is_admin(message.from_user.id):
        mechanics = db.list_users_by_role(DB_PATH, "mechanic")
        if mechanics:
            await message.answer("Выберите механика:", reply_markup=mechanics_kb(mechanics, sid))
            return

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🆕 Создан сервис #{sid}, ожидает подтверждения")

    await message.answer(f"Сервис #{sid} создан")

# ================= PENDING / HISTORY =================
@dp.callback_query(F.data == "service:pending")
async def services_pending(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user.id):
        return

    services = db.list_pending_services(DB_PATH)
    if not services:
        await call.message.answer("Нет ожидающих сервисов")
        return

    for s in services:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"service:admin_approve:{s['id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"service:admin_reject:{s['id']}")
            ]
        ])
        await call.message.answer(
            f"#{s['id']} | {s['plate']} | {s['desired_at']}\n{s['description']}",
            reply_markup=kb
        )


@dp.callback_query(F.data == "service:history")
async def services_history(call: CallbackQuery):
    role = get_role(call.from_user.id)
    services = (
        db.list_service_history(DB_PATH)
        if role == "admin"
        else db.list_service_history(DB_PATH, call.from_user.id)
    )

    if not services:
        await call.message.answer("История пуста")
        return

    for s in services:
        await call.message.answer(
            f"#{s['id']} | {s['plate']}\n"
            f"{s['comments']}\n"
            f"Стоимость: {s['cost_net']}"
        )

# ================= ASSIGN / FINISH =================
@dp.callback_query(F.data.startswith("service:assign"))
async def assign_mechanic(call: CallbackQuery):
    _, _, sid, mech = call.data.split(":")
    mech_id = None if mech == "none" else int(mech)
    db.assign_mechanic(DB_PATH, int(sid), mech_id)
    if mech_id:
        await bot.send_message(mech_id, f"Вам назначен сервис #{sid}")
    await call.message.answer("Назначено")


@dp.message(F.text == BTN_MY_SERVICES)
async def my_services(message: Message):
    services = db.get_services_for_mechanic(DB_PATH, message.from_user.id)
    if not services:
        await message.answer("Нет сервисов")
        return

    for s in services:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Завершить", callback_data=f"service:finish:{s['id']}")
        ]])
        await message.answer(
            f"#{s['id']} | {s['plate']} | {s['desired_at']}\n{s['description']}",
            reply_markup=kb
        )


@dp.callback_query(F.data.startswith("service:finish"))
async def finish_service(call: CallbackQuery, state: FSMContext):
    sid = int(call.data.split(":")[2])
    await state.set_state(FinishServiceStates.mileage)
    await state.update_data(service_id=sid)
    await call.message.answer("Финальный пробег:")


@dp.message(FinishServiceStates.mileage)
async def finish_mileage(message: Message, state: FSMContext):
    await state.update_data(mileage=int(message.text))
    await state.set_state(FinishServiceStates.cost)
    await message.answer("Стоимость NETTO:")


@dp.message(FinishServiceStates.cost)
async def finish_cost(message: Message, state: FSMContext):
    await state.update_data(cost=float(message.text))
    await state.set_state(FinishServiceStates.comment)
    await message.answer("Комментарий:")


@dp.message(FinishServiceStates.comment)
async def finish_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    db.set_service_result(
        DB_PATH,
        data["service_id"],
        data["mileage"],
        data["cost"],
        message.text
    )
    await state.clear()

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"✅ Сервис #{data['service_id']} завершён")

    await message.answer("Сервис завершён")

# ================= START BOT =================
async def main():
    db.init_db(DB_PATH)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
