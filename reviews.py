import logging
from aiogram import types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from database import db_pool

class ReviewStates(StatesGroup):
    waiting_review_text = State()
    waiting_review_media = State()

REVIEWS_CHANNEL_ID = -1002513508156
ADMIN_ID = 957724800
MIN_REVIEW_INTERVAL = timedelta(minutes=5)

def register_reviews_handlers(dp, bot):

    @dp.callback_query(F.data == "start_review")
    async def start_review(call: types.CallbackQuery, state: FSMContext):

        async with db_pool.acquire() as conn:
            has_reviewed = await conn.fetchval("""
                SELECT has_reviewed 
                FROM user_access 
                WHERE user_id = $1
            """, call.from_user.id)

        if has_reviewed:
            await call.answer("❌ Вы уже оставили отзыв!", show_alert=True)
            return
        
        user = call.from_user
        now = datetime.now()

        data = await state.get_data()
        last_time = data.get("last_review_time")

        if last_time:
            last_time_dt = datetime.fromisoformat(last_time)
            if now - last_time_dt < MIN_REVIEW_INTERVAL:
                remaining = (MIN_REVIEW_INTERVAL - (now - last_time_dt)).seconds // 60
                await call.answer(f"⏳ Подождите {remaining} мин. перед повторной отправкой.", show_alert=True)
                return

        await state.update_data(user_id=user.id, username=user.username, last_review_time=now.isoformat())

        await call.message.answer(
            "✍️ Напишите ваш отзыв (максимум 500 символов):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_review")]]
            )
        )
        await state.set_state(ReviewStates.waiting_review_text)

    @dp.callback_query(F.data == "cancel_review")
    async def cancel_review(call: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.edit_text("❌ Отзыв отменён.")
        await call.answer()

    @dp.message(ReviewStates.waiting_review_text)
    async def process_review_text(message: types.Message, state: FSMContext):
        if len(message.text) > 500:
            return await message.answer("❌ Превышен лимит символов!")

        await state.update_data(review_text=message.text)
        await message.answer(
            "📎 Хотите прикрепить фото или видео?\nОтправьте файл или нажмите 👇",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_media")]]
            )
        )
        await state.set_state(ReviewStates.waiting_review_media)

    @dp.message(ReviewStates.waiting_review_media, F.photo | F.video)
    async def handle_review_media(message: types.Message, state: FSMContext):
        if message.photo:
            await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
        elif message.video:
            await state.update_data(media_id=message.video.file_id, media_type="video")

        await send_review_to_admin(bot, state)
        await message.answer("✅ Отзыв отправлен на модерацию!")
        await state.clear()

    @dp.callback_query(F.data == "skip_media")
    async def skip_media(call: types.CallbackQuery, state: FSMContext):
        await send_review_to_admin(bot, state)
        await call.message.answer("✅ Отзыв отправлен на модерацию!")
        await state.clear()

    @dp.callback_query(F.data.startswith("approve_"))
    async def approve_review(call: types.CallbackQuery):
        user_id = int(call.data.split("_")[1])

        async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE user_access 
                    SET has_reviewed = TRUE 
                    WHERE user_id = $1
                """, user_id)
        
        await bot.send_message(user_id, "🎉 Ваш отзыв был одобрен!")

        text = call.message.caption or call.message.text or ""
        review_text = text.split("\n\n", 1)[-1].strip()

        if call.message.photo:
            await bot.send_photo(REVIEWS_CHANNEL_ID, call.message.photo[-1].file_id,
                                 caption=f"🌟 Новый отзыв!\n\n{review_text}")
        elif call.message.video:
            await bot.send_video(REVIEWS_CHANNEL_ID, call.message.video.file_id,
                                 caption=f"🌟 Новый отзыв!\n\n{review_text}")
        else:
            await bot.send_message(REVIEWS_CHANNEL_ID, f"🌟 Новый отзыв!\n\n{review_text}")

        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Отзыв одобрен и опубликован.")

    @dp.callback_query(F.data.startswith("reject_"))
    async def reject_review(call: types.CallbackQuery):
        user_id = int(call.data.split("_")[1])
        await bot.send_message(user_id, "😔 Ваш отзыв был отклонён.")
        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Отзыв отклонён.")

async def send_review_to_admin(bot, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    username = data.get("username") or "Без username"
    text = data.get("review_text")
    media_id = data.get("media_id")
    media_type = data.get("media_type")

    caption = f"📨 Отзыв от пользователя:\n🆔 ID: {user_id}\n👤 Username: @{username}\n\n{text}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
    ]])

    if media_type == "photo":
        await bot.send_photo(ADMIN_ID, media_id, caption=caption, reply_markup=kb)
    elif media_type == "video":
        await bot.send_video(ADMIN_ID, media_id, caption=caption, reply_markup=kb)
    else:
        await bot.send_message(ADMIN_ID, caption, reply_markup=kb)
