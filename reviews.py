from aiogram import types, F, Dispatcher
from aiogram.fsm.state import State, StatesGroup, StateFilter
from aiogram.fsm.context import FSMContext
from database import get_db_connection
from datetime import datetime

class ReviewStates(StatesGroup):
    waiting_review_text = State()
    waiting_review_media = State()

REVIEWS_CHANNEL_ID = -1002513508156
dp = Dispatcher()

def register_reviews_handlers(dp, bot, REVIEWS_CHANNEL_ID):
    @dp.callback_query(F.data == "start_review_")
    async def start_review(call: types.CallbackQuery, state: FSMContext):
        await call.message.answer(
            "✍️ Напишите ваш отзыв (максимум 500 символов):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_review")]
            ])
        )
        await state.set_state("waiting_review")
    
    @dp.message(ReviewStates.waiting_review_text)
    async def process_review(message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        
        if len(message.text) > 500:
            return await message.answer("❌ Превышен лимит символов!")
      
        mod_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить", 
                    callback_data=f"approve_{user_id}_{message.message_id}" 
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", 
                    callback_data=f"reject_{user_id}"
                )
            ]
        ])
        
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📨 Отзыв от пользователя {user_id}:\n\n{message.text}",
            reply_markup=mod_kb
        )
        
        await message.answer("✅ Отзыв отправлен на модерацию!")
        await state.clear()
    
    @dp.callback_query(F.data.startswith("approve_"))
    async def approve_review(call: types.CallbackQuery):
        _, user_id, message_id = call.data.split("_")
     
        await bot.send_message(
            chat_id=int(user_id),
            text="🎉 Ваш отзыв был одобрен!"
        )
       
        original_text = call.message.text
        await bot.send_message(
            chat_id=REVIEWS_CHANNEL_ID,
            text=f"🌟 Одобренный отзыв:\n\n{original_text.split(':', 1)[-1].strip()}"
        )
        
        await call.message.edit_reply_markup(reply_markup=None) 
    
    @dp.callback_query(F.data.startswith("reject_"))
    async def reject_review(call: types.CallbackQuery):
        _, user_id = call.data.split("_")
        
        await bot.send_message(
            chat_id=int(user_id),
            text="😔 Ваш отзыв был отклонен."
        )
        
        await call.message.delete()
