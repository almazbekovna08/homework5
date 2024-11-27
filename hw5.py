from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import asyncio
import logging
from config import token

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())

connect = sqlite3.connect("bank_bot.db")
cursor = connect.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    balance REAL DEFAULT 0
);
""")
connect.commit()

class Registration(StatesGroup):
    full_name = State()

class TransferState(StatesGroup):
    amount = State()
    recipient = State()

def register_user(user_id, username, full_name):
    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)
    """, (user_id, username, full_name))
    connect.commit()

def is_registered(user_id: int) -> bool:
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if is_registered(user_id):
        await message.answer("Вы уже зарегистрированы! Используйте команды /balance или /transfer.")
    else:
        await message.answer("Добро пожаловать! Пожалуйста, введите ваше полное имя:")
        await state.set_state(Registration.full_name)

@dp.message(Registration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите ваше полное имя (имя и фамилию).")
        return

    user_id = message.from_user.id
    username = message.from_user.username or "Не указан"

    register_user(user_id, username, full_name)
    await message.answer(
        f"Спасибо, {full_name}! Вы успешно зарегистрированы.\n"
        "Теперь вы можете проверить баланс с помощью команды /balance или перевести деньги с помощью /transfer."
    )
    await state.clear()

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    if not is_registered(user_id):
        await message.answer("Вы не зарегистрированы. Пожалуйста, используйте команду /start для регистрации.")
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        balance = result[0]
        await message.answer(f"Ваш текущий баланс: {balance} сом.")
    else:
        await message.answer("Произошла ошибка при получении данных. Пожалуйста, попробуйте позже.")

@dp.message(Command("transfer"))
async def cmd_transfer(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_registered(user_id):
        await message.answer("Вы не зарегистрированы. Пожалуйста, используйте команду /start для регистрации.")
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result[0] == 0:
        await message.answer("У вас недостаточно средств для перевода.")
        return

    await message.answer("Введите сумму для перевода:")
    await state.set_state(TransferState.amount)



@dp.message(TransferState.amount)
async def process_transfer_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма перевода должна быть положительной. Попробуйте снова.")
            return

        user_id = message.from_user.id
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()


        if result and result[0] < amount:
            await message.answer("У вас недостаточно средств для перевода.")
            await state.clear()
            return

        await state.update_data(amount=amount)
        await message.answer("Введите ID получателя:")
        await state.set_state(TransferState.recipient)
    except ValueError:
        await message.answer("Пожалуйста, введите числовое значение суммы.")

@dp.message(TransferState.recipient)
async def process_transfer_recipient(message: types.Message, state: FSMContext):
    try:
        recipient_id = int(message.text)
        user_id = message.from_user.id

        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (recipient_id,))
        recipient_exists = cursor.fetchone()

        if not recipient_exists:
            await message.answer("Получатель с таким ID не найден.")
            await state.clear()
            return

        data = await state.get_data()
        amount = data['amount']

        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, recipient_id))
        connect.commit()

        await message.answer(f"Перевод {amount} сом успешно выполнен.")
        await bot.send_message(recipient_id, f"Вы получили перевод {amount} сом от пользователя {user_id}.")
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID получателя.")

@dp.errors()
async def handle_error(update: types.Update, exception: Exception):
    logging.exception(f"Произошла ошибка: {exception}")
    return True

async def main():
        await dp.start_polling(bot)
if __name__=='__main__':
    try:
         asyncio.run(main())
    except KeyboardInterrupt:
        print('Выход')