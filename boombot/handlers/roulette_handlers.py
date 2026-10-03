import logging
import random
from decimal import Decimal, InvalidOperation
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes

# Import with updated paths
from boombot.games.roulette.roulette import (
    get_roulette_main_keyboard, get_bet_type_keyboard, get_number_selection_keyboard,
    get_bet_amount_keyboard, get_roulette_status, reset_player_roulette,
    get_roulette_help_text, place_bet, play_roulette_round,
    CALLBACK_SPIN, CALLBACK_SHOW, CALLBACK_RESET, CALLBACK_HELP,
    CALLBACK_BET_MENU, CALLBACK_BACK_TO_MAIN, CALLBACK_BET_TYPE_PREFIX,
    CALLBACK_BET_NUMBER_PREFIX, CALLBACK_BET_AMOUNT_PREFIX
)
from boombot.core.data_manager import get_data_manager

# Initialize logger
logger = logging.getLogger(__name__)
data_manager = get_data_manager()

async def start_roulette_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a roulette game session."""
    # Get user and chat information
    user = update.effective_user
    chat = update.effective_chat
    
    if not chat or not user:
        return
    
    channel_id = str(chat.id)
    user_id = str(user.id)
    user_name = user.full_name
    channel_name = chat.title if chat.title else f"Chat {channel_id}"
    
    # Make sure user has a player record with roulette data
    player_data = data_manager.get_player_data(channel_id, user_id)
    if 'balance' not in player_data:
        player_data['balance'] = '100.00'  # Starting balance
        player_data['display_name'] = user_name
        player_data['roulette_bets'] = {}
        data_manager.save_player_data(channel_id, user_id, player_data)
    
    # Get status message and keyboard
    status_message = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
    keyboard = get_roulette_main_keyboard()
    
    await update.message.reply_text(
        # Escape the '!' character for MarkdownV2
        text=f"🎰 Welcome to Roulette\\! 🎰\n\n{status_message}",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )

async def roulette_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all callbacks for the roulette game."""
    query = update.callback_query
    await query.answer()  # Answer callback query to remove the loading indicator
    
    # Get user and chat information
    user = update.effective_user
    chat = update.effective_chat
    
    if not chat or not user:
        return
    
    channel_id = str(chat.id)
    user_id = str(user.id)
    user_name = user.full_name
    channel_name = chat.title if chat.title else f"Chat {channel_id}"
    
    callback_data = query.data
    
    # Get player data
    player_data = data_manager.get_player_data(channel_id, user_id)
    balance = Decimal(player_data.get('balance', '0'))
    
    # Handle different callback actions
    try:
        if callback_data == CALLBACK_SPIN:
            # Spin the wheel and process bets
            result_message = play_roulette_round(channel_id, data_manager)
            
            # Add updated status and main keyboard
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"{result_message}\n\n{status}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data == CALLBACK_SHOW:
            # Show current game status
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"🎰 Roulette Game Status 🎰\n\n{status}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data == CALLBACK_RESET:
            # Reset player's game
            reset_message = reset_player_roulette(channel_id, user_id, user_name, data_manager)
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"🔄 Game Reset\n\n{reset_message}\n\n{status}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data == CALLBACK_HELP:
            # Show help text
            help_text = get_roulette_help_text()
            await query.edit_message_text(
                text=f"{help_text}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data == CALLBACK_BET_MENU:
            # Show bet type selection menu
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"🎲 Select Bet Type\n\n{status}",
                reply_markup=get_bet_type_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data == CALLBACK_BACK_TO_MAIN:
            # Return to main menu
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"🎰 Roulette Game\n\n{status}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data.startswith(CALLBACK_BET_TYPE_PREFIX):
            # Handle bet type selection
            bet_type = callback_data[len(CALLBACK_BET_TYPE_PREFIX):]
            
            if bet_type == 'straight':
                # For straight bets, show number selection
                await query.edit_message_text(
                    text="🔢 Select Number for Straight Bet",
                    reply_markup=get_number_selection_keyboard(),
                    parse_mode="MarkdownV2"
                )
            else:
                # For other bet types, go to amount selection
                await query.edit_message_text(
                    text=f"💰 Select Bet Amount for {bet_type.replace('_', ' ').title()}",
                    reply_markup=get_bet_amount_keyboard(bet_type, "", balance),
                    parse_mode="MarkdownV2"
                )
        
        elif callback_data.startswith(CALLBACK_BET_NUMBER_PREFIX):
            # Handle number selection for straight bets
            number = callback_data[len(CALLBACK_BET_NUMBER_PREFIX):]
            await query.edit_message_text(
                text=f"💰 Select Bet Amount for Number {number}",
                reply_markup=get_bet_amount_keyboard("straight", number, balance),
                parse_mode="MarkdownV2"
            )
        
        elif callback_data.startswith(CALLBACK_BET_AMOUNT_PREFIX):
            # Handle bet amount selection
            bet_info = callback_data[len(CALLBACK_BET_AMOUNT_PREFIX):].split('_')
            
            if len(bet_info) == 3:  # Straight bet (type_number_amount)
                bet_type, bet_value, amount = bet_info
                result = place_bet(channel_id, user_id, user_name, bet_type, bet_value, amount, data_manager)
            else:  # Other bet types (type_amount)
                bet_type, amount = bet_info
                result = place_bet(channel_id, user_id, user_name, bet_type, "", amount, data_manager)
            
            # Show bet result and status
            status = get_roulette_status(channel_id, user_id, user_name, channel_name, data_manager)
            await query.edit_message_text(
                text=f"🎲 {result}\n\n{status}",
                reply_markup=get_roulette_main_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        logger.error(f"Error handling roulette callback: {e}")
        await query.edit_message_text(
            text=f"❌ An error occurred: {str(e)}\n\nPlease try again.",
            reply_markup=get_roulette_main_keyboard(),
            parse_mode="MarkdownV2"
        )