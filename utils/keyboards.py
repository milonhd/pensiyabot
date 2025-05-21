from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from config import PAYMENT_URL

# Основная клавиатура с выбором тарифов
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Уровень САМОСТОЯТЕЛЬНЫЙ", callback_data="self")],
    [InlineKeyboardButton(text="Уровень БАЗОВЫЙ", callback_data="basic")],
    [InlineKeyboardButton(text="Уровень ПРО", callback_data="pro")],
])

# Клавиатура для доступа к материалам
materials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏰 Получить материалы", callback_data="get_materials")]
])

def get_main_menu_keyboard(is_admin=False):
    """Основная клавиатура в главном меню"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="📄 Публичная оферта")
    kb.button(text="📞 Поддержка")
    
    if is_admin:
        kb.button(text="📢 Рассылка")
    
    kb.adjust(2)  # 2 кнопки в ряд
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отменить")
    return kb.as_markup(resize_keyboard=True)

def get_confirm_keyboard():
    """Клавиатура для подтверждения действия"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="✅ Подтвердить рассылку")
    kb.button(text="❌ Отменить")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def get_self_years_keyboard():
    """Клавиатура для выбора года выхода на пенсию"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Пенсия {year}", callback_data=f"year_{year}")] 
        for year in range(2025, 2032)
    ])

def get_payment_keyboard(year=None, tariff=None):
    """Клавиатура для оплаты и отправки чека"""
    callback_data = f"send_screenshot_{year}" if year else f"send_screenshot_{tariff}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url=PAYMENT_URL)],
        [InlineKeyboardButton(text="📄 Отправить чек", callback_data=callback_data)]
    ])
