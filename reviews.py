from aiogram import types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class ReviewStates(StatesGroup):
    waiting_review_text = State()
    waiting_review_media = State()

REVIEWS_CHANNEL_ID = -1002513508156
ADMIN_ID = 957724800

def register_reviews_handlers(dp, bot):

    @dp.callback_query(F.data == "start_review")
    async def start_review(call: types.CallbackQuery, state: FSMContext):
        user = call.from_user
        await state.update_data(user_id=user.id, username=user.username)
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
        data = await state.get_data()
        await state.update_data(review_text=message.text)

        await message.answer(
            "📎 Хотите прикрепить фото или видео?\nОтправьте файл или нажмите 'Пропустить'.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_media")]]
            )
        )
        await state.set_state(ReviewStates.waiting_review_media)

    @dp.message(ReviewStates.waiting_review_media, F.photo | F.video)
    async def handle_media(message: types.Message, state: FSMContext):
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
    async def approve_review(call: types.CallbackQuery, state: FSMContext):
        parts = call.data.split("_")
        user_id = int(parts[1])

        await bot.send_message(user_id, "🎉 Ваш отзыв был одобрен!")
    
        text = call.message.caption or call.message.text or ""
        media = None
        media_type = None
    
        if call.message.photo:
            media = call.message.photo[-1].file_id
            media_type = "photo"
        elif call.message.video:
            media = call.message.video.file_id
            media_type = "video"
    
        review_text = text.split(":", 2)[-1].strip()
    
        if media and media_type == "photo":
            await bot.send_photo(
                chat_id=REVIEWS_CHANNEL_ID,
                photo=media,
                caption=f"🌟 Одобренный отзыв:\n\n{review_text}"
            )
        elif media and media_type == "video":
            await bot.send_video(
                chat_id=REVIEWS_CHANNEL_ID,
                video=media,
                caption=f"🌟 Одобренный отзыв:\n\n{review_text}"
            )
        else:
            await bot.send_message(
                chat_id=REVIEWS_CHANNEL_ID,
                text=f"🌟 Одобренный отзыв:\n\n{review_text}"
            )
    
        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Отзыв одобрен и опубликован.")

    @dp.callback_query(F.data.startswith("reject_"))
    async def reject_review(call: types.CallbackQuery):
        user_id = call.data.split("_")[1]
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
        await bot.send_photo(ADMIN_ID, photo=media_id, caption=caption, reply_markup=kb)
    elif media_type == "video":
        await bot.send_video(ADMIN_ID, video=media_id, caption=caption, reply_markup=kb)
    else:
        await bot.send_message(ADMIN_ID, text=caption, reply_markup=kb)
