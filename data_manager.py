import json
import logging
import os
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from config import ANSWERS_FILE, GAME_DATA_FILE # Assuming GAME_DATA_FILE is defined in config

logger = logging.getLogger(__name__)

# --- Existing Question/Answer Logic (kept separate for now) ---
# Store only the count now {normalized_question: count}
question_answers: dict[str, int] = {}

def load_answers():
    """Loads question answers from the JSON file."""
    global question_answers
    if ANSWERS_FILE.exists():
        try:
            with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
                # Ensure loaded values are integers
                loaded_data = json.load(f)
                # Filter out potential non-string keys or non-int values if file was manually edited
                question_answers = {str(k): int(v) for k, v in loaded_data.items() if isinstance(k, str) and isinstance(v, (int, float))}
        except (json.JSONDecodeError, IOError, ValueError, TypeError) as e:
            logger.error(f"Error loading or parsing answers file: {e}")
            question_answers = {} # Reset if file is corrupt or invalid format
    else:
        question_answers = {}


def save_answers():
    """Saves the current question answers to the JSON file."""
    global question_answers
    try:
        with open(ANSWERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(question_answers, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logger.error(f"Error saving answers file: {e}")

def get_answers() -> dict[str, int]:
    """Returns the current question answers dictionary."""
    return question_answers

def update_answer(key: str, value: int):
    """Updates or adds an answer to the dictionary."""
    global question_answers
    question_answers[key] = value

# --- New DataManager Class for Game State ---

class DataManager:
    def __init__(self, data_file: Path = GAME_DATA_FILE):
        """Initializes the DataManager.

        Args:
            data_file: The path to the JSON file used for storing game data.
        """
        self.data_file = data_file
        # Structure: {channel_id: {'channel_state': {...}, 'players': {user_id: {...}}}} 
        self.data = self._load_data()

    def _load_data(self) -> defaultdict:
        """Loads game data from the JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    # Use defaultdict for easier handling of new channels/players
                    loaded = json.load(f)
                    # Convert numeric strings back to Decimal where appropriate (e.g., balance, bets)
                    # This needs careful handling based on actual data structure
                    # For now, load as is, conversion happens in getter/setter logic
                    return defaultdict(lambda: {'channel_state': {}, 'players': defaultdict(dict)}, loaded)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading game data file {self.data_file}: {e}")
                # Return a default structure if loading fails
                return defaultdict(lambda: {'channel_state': {}, 'players': defaultdict(dict)})
        else:
            # Return a default structure if file doesn't exist
            return defaultdict(lambda: {'channel_state': {}, 'players': defaultdict(dict)})

    def _save_data(self):
        """Saves the current game data to the JSON file."""
        try:
            # Ensure parent directory exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                # Convert defaultdicts back to regular dicts for JSON serialization
                data_to_save = {k: {'channel_state': v['channel_state'], 'players': dict(v['players'])} 
                                for k, v in self.data.items()}
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error saving game data file {self.data_file}: {e}")

    # --- Channel Data Methods ---
    def get_channel_data(self, channel_id: str) -> dict:
        """Gets the state data for a specific channel (e.g., craps state, point)."""
        # defaultdict ensures channel_id exists with default value if not present
        return self.data[str(channel_id)]['channel_state']

    def save_channel_data(self, channel_id: str, data: dict):
        """Saves the state data for a specific channel."""
        channel_id_str = str(channel_id)
        # Ensure the basic structure exists
        if channel_id_str not in self.data:
             self.data[channel_id_str] = {'channel_state': {}, 'players': defaultdict(dict)}
        self.data[channel_id_str]['channel_state'] = data
        self._save_data()

    # --- Player Data Methods ---
    def get_player_data(self, channel_id: str, user_id: str) -> dict:
        """Gets the data for a specific player within a channel.
           Initializes player data with defaults if the player is new.
        """
        channel_id_str = str(channel_id)
        user_id_str = str(user_id)
        player_data = self.data[channel_id_str]['players'].get(user_id_str)
        
        if player_data is None:
            # Initialize default player data (e.g., starting balance)
            player_data = {
                'balance': '100.00', # Store as string for JSON compatibility
                'craps_bets': {}
                # Add other game-specific or general player data here
            }
            # No need to save here, will be saved when modified by save_player_data
            # self.data[channel_id_str]['players'][user_id_str] = player_data 
        
        # Ensure craps_bets exists and is a dict
        if 'craps_bets' not in player_data or not isinstance(player_data.get('craps_bets'), dict):
            player_data['craps_bets'] = {}
            
        return player_data

    def save_player_data(self, channel_id: str, user_id: str, data: dict):
        """Saves the data for a specific player within a channel."""
        channel_id_str = str(channel_id)
        user_id_str = str(user_id)
        # Ensure the basic structure exists
        if channel_id_str not in self.data:
             self.data[channel_id_str] = {'channel_state': {}, 'players': defaultdict(dict)}
        elif 'players' not in self.data[channel_id_str]:
             self.data[channel_id_str]['players'] = defaultdict(dict)
             
        self.data[channel_id_str]['players'][user_id_str] = data
        self._save_data()

    # --- Helper Methods (as described in craps_game.py docstring) ---
    def get_players_with_bets(self, channel_id: str, game: str = 'craps') -> dict[str, dict]:
        """Gets data for players in a channel who have active bets for a specific game."""
        channel_id_str = str(channel_id)
        players = self.data[channel_id_str]['players']
        bet_key = f'{game}_bets' # e.g., 'craps_bets'
        return {
            user_id: p_data
            for user_id, p_data in players.items()
            if p_data.get(bet_key) # Check if the bet dictionary exists and is not empty
        }

    def get_all_players_data(self, channel_id: str) -> dict[str, dict]:
        """Gets all player data for a specific channel."""
        channel_id_str = str(channel_id)
        # Return a copy to prevent direct modification of internal defaultdict
        return dict(self.data[channel_id_str]['players'])

# --- Initialization --- 
# Load answers on startup
load_answers()

# Create a global instance of DataManager if needed by handlers
# Or instantiate it where needed (e.g., in bot.py)
# game_data_manager = DataManager()
