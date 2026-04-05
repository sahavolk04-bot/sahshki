import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from game import CheckersGame, EMPTY, WHITE, BLACK, WHITE_KING, BLACK_KING
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
db = Database("leaderboard.db")

# active_games[chat_id] = CheckersGame
active_games = {}
# pending_challenges[chat_id] = {"challenger": user_id, "challenger_name": str}
pending_challenges = {}


def board_to_keyboard(game: CheckersGame, selected: tuple = None) -> InlineKeyboardMarkup:
    """Convert game board to inline keyboard."""
    keyboard = []
    valid_moves = []
    if selected:
        valid_moves = game.get_valid_moves_for_piece(selected[0], selected[1])

    for row in range(8):
        kb_row = []
        for col in range(8):
            cell = game.board[row][col]
            is_dark = (row + col) % 2 == 1

            # Cell content
            if cell == WHITE:
                text = "🟡"  # жёлтая шашка
            elif cell == BLACK:
                text = "🟤"  # коричневая шашка
            elif cell == WHITE_KING:
                text = "🌟"  # жёлтая дамка
            elif cell == BLACK_KING:
                text = "💫"  # коричневая дамка
            elif selected and (row, col) == selected:
                text = "✳️"
            elif (row, col) in valid_moves:
                text = "🟢"
            elif is_dark:
                text = "◼️"
            else:
                text = "◻️"

            # Callback data
            cb = f"move_{row}_{col}"
            kb_row.append(InlineKeyboardButton(text, callback_data=cb))

        keyboard.append(kb_row)

    # Bottom controls
    keyboard.append([
        InlineKeyboardButton("🏳️ Сдаться", callback_data="resign"),
        InlineKeyboardButton("📊 Счёт", callback_data="score"),
    ])
    return InlineKeyboardMarkup(keyboard)


def game_status_text(game: CheckersGame, chat_id: int) -> str:
    b_name = game.black_name
    w_name = game.white_name
    current = b_name if game.current_turn == BLACK else w_name
    symbol = "🟤" if game.current_turn == BLACK else "🟡"
    b_count = sum(1 for r in game.board for c in r if c in (BLACK, BLACK_KING))
    w_count = sum(1 for r in game.board for c in r if c in (WHITE, WHITE_KING))
    return (
        f"♟ *Шашки*\n"
        f"🟤 {b_name}: {b_count} шашек\n"
        f"🟡 {w_name}: {w_count} шашек\n\n"
        f"Ход: {symbol} *{current}*"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♟ *Бот для игры в шашки!*\n\n"
        "Команды:\n"
        "/play — вызов на партию\n"
        "/accept — принять вызов\n"
        "/resign — сдаться\n"
        "/leaderboard — таблица лидеров\n"
        "/rules — правила\n\n"
        "_Только для групповых чатов!_",
        parse_mode="Markdown"
    )


async def play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в групповых чатах!")
        return

    if chat_id in active_games:
        await update.message.reply_text("⚠️ В этом чате уже идёт игра! Дождитесь её окончания.")
        return

    if chat_id in pending_challenges:
        ch = pending_challenges[chat_id]
        if ch["challenger"] == user.id:
            await update.message.reply_text("⏳ Ты уже бросил вызов! Ожидай соперника.")
            return

    pending_challenges[chat_id] = {
        "challenger": user.id,
        "challenger_name": user.first_name
    }

    await update.message.reply_text(
        f"⚔️ *{user.first_name}* бросает вызов!\n\n"
        f"Кто хочет сыграть в шашки? Напиши /accept чтобы принять вызов!\n"

        f"_(Вызов действителен 5 минут)_",
        parse_mode="Markdown"
    )

    # Auto-cancel after 5 minutes
    context.job_queue.run_once(
        cancel_challenge,
        300,
        data={"chat_id": chat_id, "challenger_id": user.id},
        name=f"challenge_{chat_id}"
    )


async def cancel_challenge(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    if chat_id in pending_challenges:
        ch = pending_challenges.pop(chat_id)
        await context.bot.send_message(
            chat_id,
            f"⏰ Вызов от *{ch['challenger_name']}* истёк.",
            parse_mode="Markdown"
        )


async def accept_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в групповых чатах!")
        return

    if chat_id not in pending_challenges:
        await update.message.reply_text("🤷 Нет активных вызовов. Напиши /play чтобы бросить вызов!")
        return

    ch = pending_challenges.pop(chat_id)
    if ch["challenger"] == user.id:
        await update.message.reply_text("❌ Нельзя принять собственный вызов!")
        pending_challenges[chat_id] = ch
        return

    # Cancel pending job
    jobs = context.job_queue.get_jobs_by_name(f"challenge_{chat_id}")
    for job in jobs:
        job.schedule_removal()

    # Black goes first (challenger), White is acceptor
    game = CheckersGame(
        black_id=ch["challenger"],
        black_name=ch["challenger_name"],
        white_id=user.id,
        white_name=user.first_name
    )
    active_games[chat_id] = game

    msg = await update.message.reply_text(
        f"🎮 *Игра началась!*\n\n"
        f"🟤 {ch['challenger_name']} vs 🟡 {user.first_name}\n\n"
        f"{game_status_text(game, chat_id)}",
        parse_mode="Markdown",
        reply_markup=board_to_keyboard(game)
    )
    game.message_id = msg.message_id
    game.chat_id = chat_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    user = query.from_user

    if chat_id not in active_games:
        await query.answer("Игра не найдена!", show_alert=True)
        return

    game = active_games[chat_id]

    # --- RESIGN ---
    if query.data == "resign":
        if user.id not in (game.black_id, game.white_id):
            await query.answer("Ты не участник этой игры!", show_alert=True)
            return
        winner_name = game.white_name if user.id == game.black_id else game.black_name
        winner_id = game.white_id if user.id == game.black_id else game.black_id
        loser_id = user.id
        db.record_win(winner_id, winner_name)
        db.record_loss(loser_id, user.first_name)
        del active_games[chat_id]
        await query.edit_message_text(
            f"🏳️ *{user.first_name}* сдался!\n\n🏆 Победитель: *{winner_name}*",
            parse_mode="Markdown"
        )
        return

    # --- SCORE ---
    if query.data == "score":
        b_count = sum(1 for r in game.board for c in r if c in (BLACK, BLACK_KING))
        w_count = sum(1 for r in game.board for c in r if c in (WHITE, WHITE_KING))
        await query.answer(
            f"🟤 {game.black_name}: {b_count}\n🟡 {game.white_name}: {w_count}",
            show_alert=True
        )
        return

    # --- MOVE ---
    if not query.data.startswith("move_"):
        return

    _, row, col = query.data.split("_")
    row, col = int(row), int(col)

    # Check it's the player's turn
    if game.current_turn == BLACK and user.id != game.black_id:
        await query.answer("Сейчас ход 🟤!", show_alert=True)
        return
    if game.current_turn == WHITE and user.id != game.white_id:
        await query.answer("Сейчас ход 🟡!", show_alert=True)
        return

    cell = game.board[row][col]

    # Select a piece
    if game.selected is None:
        own_pieces = (BLACK, BLACK_KING) if game.current_turn == BLACK else (WHITE, WHITE_KING)
        if cell not in own_pieces:
            await query.answer("Выбери свою шашку!", show_alert=True)
            return
        moves = game.get_valid_moves_for_piece(row, col)
        if not moves:
            await query.answer("Эта шашка не может ходить!", show_alert=True)
            return
        game.selected = (row, col)
        await query.edit_message_text(
            game_status_text(game, chat_id),
            parse_mode="Markdown",
            reply_markup=board_to_keyboard(game, selected=game.selected)
        )
        return

    # Deselect if clicking same piece
    if game.selected == (row, col):
        game.selected = None
        await query.edit_message_text(
            game_status_text(game, chat_id),
            parse_mode="Markdown",
            reply_markup=board_to_keyboard(game)
        )
        return

    # Try to move
    valid_moves = game.get_valid_moves_for_piece(game.selected[0], game.selected[1])
    if (row, col) not in valid_moves:
        # Maybe selecting another own piece
        own_pieces = (BLACK, BLACK_KING) if game.current_turn == BLACK else (WHITE, WHITE_KING)
        if cell in own_pieces:
            moves = game.get_valid_moves_for_piece(row, col)
            if moves:
                game.selected = (row, col)
                await query.edit_message_text(
                    game_status_text(game, chat_id),
                    parse_mode="Markdown",
                    reply_markup=board_to_keyboard(game, selected=game.selected)
                )
                return
        await query.answer("Недопустимый ход!", show_alert=True)
        return

    # Execute move
    result = game.make_move(game.selected, (row, col))
    game.selected = None

    # Check win condition
    winner = game.check_winner()
    if winner:
        if winner == BLACK:
            w_id, w_name, l_id, l_name = game.black_id, game.black_name, game.white_id, game.white_name
        else:
            w_id, w_name, l_id, l_name = game.white_id, game.white_name, game.black_id, game.black_name

        db.record_win(w_id, w_name)
        db.record_loss(l_id, l_name)
        del active_games[chat_id]

        symbol = "🟤" if winner == BLACK else "🟡"
        await query.edit_message_text(
            f"🏆 *{symbol} {w_name} победил!*\n\n"
            f"Партия завершена! Напиши /leaderboard чтобы посмотреть таблицу лидеров.",
            parse_mode="Markdown"
        )
        return

    # Continue game — if multi-jump available, same player continues
    if result.get("must_continue"):
        game.selected = (row, col)
        await query.edit_message_text(
            game_status_text(game, chat_id) + "\n\n_Продолжай бить!_",
            parse_mode="Markdown",
            reply_markup=board_to_keyboard(game, selected=game.selected)
        )
    else:
        await query.edit_message_text(
            game_status_text(game, chat_id),
            parse_mode="Markdown",
            reply_markup=board_to_keyboard(game)
        )


async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_leaderboard(10)
    if not rows:
        await update.message.reply_text("📊 Таблица лидеров пуста. Сыграйте первую партию!")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *ТАБЛИЦА ЛИДЕРОВ* 🏆\n"]
    for i, (name, wins, losses, games) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        winrate = round(wins / games * 100) if games > 0 else 0
        lines.append(f"{medal} *{name}*")
        lines.append(f"   ✅ {wins}П  ❌ {losses}П  📈 {winrate}%\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def resign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in active_games:
        await update.message.reply_text("В этом чате нет активной игры.")
        return

    game = active_games[chat_id]
    if user.id not in (game.black_id, game.white_id):
        await update.message.reply_text("Ты не участник текущей игры!")
        return

    winner_name = game.white_name if user.id == game.black_id else game.black_name
    winner_id = game.white_id if user.id == game.black_id else game.black_id
    db.record_win(winner_id, winner_name)
    db.record_loss(user.id, user.first_name)
    del active_games[chat_id]

    await update.message.reply_text(
        f"🏳️ *{user.first_name}* сдался!\n🏆 Победитель: *{winner_name}*",
        parse_mode="Markdown"
    )


async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 *Правила шашек*\n\n"
        "🟤 Коричневые ходят первыми (вниз)\n"
        "🟡 Жёлтые ходят вторыми (вверх)\n\n"
        "• Обычные шашки ходят по диагонали вперёд на 1 клетку\n"
        "• Дамки (💫/🌟) ходят по диагонали в любом направлении\n"
        "• Бить нужно обязательно, если есть такая возможность\n"
        "• При достижении последнего ряда шашка становится дамкой\n"
        "• Побеждает тот, кто съел все шашки соперника или заблокировал их\n\n"
        "*Управление:*\n"
        "Нажми на свою шашку → зелёные точки 🟢 покажут возможные ходы → нажми на зелёную точку",
        parse_mode="Markdown"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("play", play_cmd))
    app.add_handler(CommandHandler("accept", accept_cmd))
    app.add_handler(CommandHandler("resign", resign_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
