import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8690815602:AAH7L_zOaCxsRA19Q6XUJlvuq8gvgj3pVno"
ADMIN_CHAT_ID = -1003705429642  # ID чата для уведомлений

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Клавиатура выбора касты
def get_cast_keyboard():
    buttons = [
        [KeyboardButton(text="Хакинг")],
        [KeyboardButton(text="DDoS")],
        [KeyboardButton(text="Осинт")],
        [KeyboardButton(text="Геоинт")],
        [KeyboardButton(text="Снос акков")],
        [KeyboardButton(text="Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Вопросы по кастам
QUESTIONS = {
    "Хакинг": [
        "1. Какие инструменты для пентеста вы знаете и какие использовали?",
        "2. Объясните разницу между black-box, white-box и grey-box тестированием.",
        "3. Как вы будете действовать при обнаружении SQL-инъекции?",
        "4. Опишите этапы эксплуатации уязвимости в веб-приложении.",
        "5. Что такое социальная инженерия и как её применяют в реальных атаках?"
    ],
    "DDoS": [
        "1. Какие типы DDoS-атак вы знаете (например, SYN-flood, UDP-flood, HTTP-flood)?",
        "2. Чем отличается атака на уровне L3/L4 от L7?",
        "3. Какие инструменты для проведения DDoS-атак вам известны?",
        "4. Как можно защититься от DDoS?",
        "5. Как выбрать мощность ботнета для успешной атаки на конкретный ресурс?"
    ],
    "Осинт": [
        "1. Какие открытые источники информации вы используете для сбора данных о цели?",
        "2. Как найти личную информацию человека по его никнейму?",
        "3. Какие методы позволяют определить местоположение по фотографии?",
        "4. Как проверить, были ли утечки данных по email или номеру телефона?",
        "5. Расскажите о техниках поиска скрытых аккаунтов в соцсетях."
    ],
    "Геоинт": [
        "1. Как по спутниковым снимкам определить тип объекта (военная база, промышленный объект)?",
        "2. Какие сервисы и инструменты вы используете для геолокации?",
        "3. Как найти координаты по фотографии с геотегами?",
        "4. Как определить временные метки на снимках и привязать их к событиям?",
        "5. Что такое анализ теней и как он помогает в геоинте?"
    ],
    "Снос акков": [
        "1. Какие методы взлома аккаунтов вы знаете (подбор пароля, фишинг, перехват сессии)?",
        "2. Как обойти двухфакторную аутентификацию?",
        "3. Как закрепиться в взломанном аккаунте, чтобы владелец не мог его восстановить?",
        "4. Как скрыть свои следы при взломе?",
        "5. Какие платформы наиболее уязвимы и почему?"
    ]
}

class ApplyForm(StatesGroup):
    choosing_cast = State()
    answering = State()
    # Для хранения индекса текущего вопроса, списка ответов, текущей касты и задачи таймера
    # Данные хранятся в data FSM

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Это бот для подачи заявок в клан. Выберите вашу касту (роль):",
        reply_markup=get_cast_keyboard()
    )
    await state.set_state(ApplyForm.choosing_cast)

# Обработка выбора касты
@dp.message(ApplyForm.choosing_cast, F.text.in_(QUESTIONS.keys()))
async def cast_chosen(message: types.Message, state: FSMContext):
    cast = message.text
    await state.update_data(cast=cast, answers=[], question_index=0)
    await state.set_state(ApplyForm.answering)
    await ask_next_question(message, state)

# Отмена заявки
@dp.message(ApplyForm.choosing_cast, F.text.lower() == "отмена")
@dp.message(ApplyForm.answering, F.text.lower() == "отмена")
async def cancel_apply(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        # Отменяем таймер, если есть
        data = await state.get_data()
        if "timer_task" in data:
            data["timer_task"].cancel()
        await state.clear()
    await message.answer("Заявка отменена.", reply_markup=ReplyKeyboardRemove())

# Если ввод не распознан на этапе выбора касты
@dp.message(ApplyForm.choosing_cast)
async def invalid_cast(message: types.Message):
    await message.answer("Пожалуйста, выберите касту из списка кнопками.")

# Вспомогательная функция для отправки следующего вопроса
async def ask_next_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cast = data["cast"]
    q_index = data["question_index"]
    questions = QUESTIONS[cast]
    
    if q_index < len(questions):
        question = questions[q_index]
        await message.answer(question, reply_markup=ReplyKeyboardRemove())
        
        # Устанавливаем таймер на 30 секунд
        loop = asyncio.get_running_loop()
        timer_task = loop.create_task(timer_timeout(message, state))
        await state.update_data(timer_task=timer_task)
    else:
        # Все вопросы заданы, отправляем результаты в админ-чат
        await finish_apply(message, state)

async def timer_timeout(message: types.Message, state: FSMContext):
    await asyncio.sleep(30)
    data = await state.get_data()
    # Проверяем, не ответил ли пользователь до таймаута (состояние может измениться)
    if await state.get_state() == ApplyForm.answering.state:
        await message.answer("Время вышло. Заявка отменена из-за отсутствия ответа.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        # Уведомляем админов о таймауте
        await bot.send_message(ADMIN_CHAT_ID, f"Заявка от {message.from_user.full_name} (@{message.from_user.username}) отменена (таймаут).")

# Обработка ответов на вопросы
@dp.message(ApplyForm.answering)
async def handle_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Отменяем таймер, если он ещё не сработал
    if "timer_task" in data:
        data["timer_task"].cancel()
    
    answers = data.get("answers", [])
    answers.append(message.text)
    await state.update_data(answers=answers, question_index=data["question_index"] + 1)
    
    await ask_next_question(message, state)

async def finish_apply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cast = data["cast"]
    answers = data["answers"]
    user = message.from_user
    
    # Формируем сообщение для админ-чата
    text = f"Новая заявка от {user.full_name} (@{user.username}) [ID: {user.id}]\n"
    text += f"Каста: {cast}\n\n"
    questions = QUESTIONS[cast]
    for i, (q, a) in enumerate(zip(questions, answers)):
        text += f"Вопрос {i+1}: {q}\nОтвет: {a}\n\n"
    
    await bot.send_message(ADMIN_CHAT_ID, text)
    await message.answer("Спасибо! Ваша заявка отправлена на рассмотрение.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
