# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Уровень САМОСТОЯТЕЛЬНЫЙ", callback_data="self")],
    [InlineKeyboardButton(text="Уровень БАЗОВЫЙ", callback_data="basic")],
    [InlineKeyboardButton(text="Уровень ПРО", callback_data="pro")],
])

materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
])

def get_self_years_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Пенсия {year}", callback_data=f"year_{year}")] for year in range(2025, 2032)
    ])

def get_year_buttons(year):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
        [InlineKeyboardButton(text="📄 Отправить чек", callback_data=f"send_screenshot_{year}")]
    ])

def get_main_menu_keyboard(admin_id, user_id):
    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="📄 Публичная оферта")
    main_kb.button(text="📞 Поддержка")

    if user_id == admin_id:
        main_kb.button(text="📢 Рассылка")

    main_kb.adjust(2)
    return main_kb.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_cancel_keyboard():
    cancel_kb = ReplyKeyboardBuilder()
    cancel_kb.button(text="❌ Отменить")
    cancel_kb.adjust(2)
    return cancel_kb.as_markup(resize_keyboard=True)

def get_confirm_broadcast_keyboard():
    confirm_kb = ReplyKeyboardBuilder()
    confirm_kb.button(text="✅ Подтвердить рассылку")
    confirm_kb.button(text="❌ Отменить")
    confirm_kb.adjust(2)
    return confirm_kb.as_markup(resize_keyboard=True)
