from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardBuilder:
    """Создание основной клавиатуры."""
    kb = ReplyKeyboardBuilder()
    kb.button(text="📄 Публичная оферта")
    kb.button(text="📞 Поддержка")
    if is_admin:
        kb.button(text="📢 Рассылка")
    kb.adjust(2)
    return kb

main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Уровень САМОСТОЯТЕЛЬНЫЙ", callback_data="self")],
    [InlineKeyboardButton(text="Уровень БАЗОВЫЙ", callback_data="basic")],
    [InlineKeyboardButton(text="Уровень ПРО", callback_data="pro")],
])

materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
])

def get_self_years_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора года выхода на пенсию."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Пенсия {year}", callback_data=f"year_{year}")] for year in range(2025, 2032)
    ])

def get_year_buttons(year: str) -> InlineKeyboardMarkup:
    """Клавиатура для оплаты и отправки чека."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url="https://pay.kaspi.kz/pay/vx2s6z0c")],
        [InlineKeyboardButton(text="📄 Отправить чек", callback_data=f"send_screenshot_{year}")]
    ])
