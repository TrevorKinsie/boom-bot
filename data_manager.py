import json
import logging
import os
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
# Import BOOM_COUNT_FILE from config
from config import ANSWERS_FILE, GAME_DATA_FILE, BOOM_COUNT_FILE

logger = logging.getLogger(__name__)

# --- DataManager Class (Singleton) for all data ---
class DataManager:
    _instance = None
    
    def __new__(cls, data_file: Path = GAME_DATA_FILE):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance.data_file = data_file
            # Structure: {channel_id: {'channel_state': {...}, 'players': {user_id: {...}}}}
            cls._instance.data = cls._instance._load_data()
            
            # Initialize boom count and answers data
            cls._instance.boom_count = 0
            cls._instance.question_answers = {}
            cls._instance.load_boom_count()
            cls._instance.load_answers()
        return cls._instance
        
    def __init__(self, data_file: Path = GAME_DATA_FILE):
        """Initializes the DataManager.

        Args:
            data_file: The path to the JSON file used for storing game data.
        """
        # The actual initialization happens in __new__
        # This prevents re-initialization if the instance already exists
        pass
    
    # --- Boom Count Methods ---
    def load_boom_count(self) -> int:
        """Loads the boom count from its JSON file."""
        if BOOM_COUNT_FILE.exists():
            try:
                with open(BOOM_COUNT_FILE, 'r') as f:
                    data = json.load(f)
                    self.boom_count = data.get("boom_count", 0)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading boom count file: {e}")
                self.boom_count = 0
        else:
            self.boom_count = 0
        return self.boom_count
    
    def save_boom_count(self):
        """Saves the current boom count to its JSON file."""
        try:
            with open(BOOM_COUNT_FILE, 'w') as f:
                json.dump({"boom_count": self.boom_count}, f)
        except IOError as e:
            logger.error(f"Error saving boom count file: {e}")
    
    def get_boom_count(self) -> int:
        """Returns the current boom count."""
        return self.boom_count
    
    def set_boom_count(self, count: int):
        """Sets and saves the boom count."""
        self.boom_count = count
        self.save_boom_count()
    
    def increment_boom_count(self):
        """Increments the boom count by 1 and saves it."""
        self.boom_count += 1
        self.save_boom_count()
    
    # --- Question/Answer Methods ---
    def load_answers(self) -> dict[str, int]:
        """Loads the answers from the JSON file."""
        try:
            if os.path.exists(ANSWERS_FILE):
                with open(ANSWERS_FILE, 'r') as f:
                    self.question_answers = json.load(f)
            else:
                self.question_answers = {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading or parsing answers file: {e}")
            self.question_answers = {}
        return self.question_answers
    
    def save_answers(self):
        """Saves the current question answers to the JSON file."""
        try:
            with open(ANSWERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.question_answers, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error saving answers file: {e}")
    
    def get_answers(self) -> dict[str, int]:
        """Returns the current question answers dictionary."""
        return self.question_answers
    
    def update_answer(self, key: str, value: int):
        """Updates or adds an answer to the dictionary and saves."""
        self.question_answers[key] = value
        self.save_answers()

    # --- Game Data Methods ---
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
                'craps_bets': {},
                'roulette_bets': {}  # Add roulette bets structure
                # Add other game-specific or general player data here
            }
            # No need to save here, will be saved when modified by save_player_data
            # self.data[channel_id_str]['players'][user_id_str] = player_data 
        
        # Ensure craps_bets exists and is a dict
        if 'craps_bets' not in player_data or not isinstance(player_data.get('craps_bets'), dict):
            player_data['craps_bets'] = {}
            
        # Ensure roulette_bets exists and is a dict
        if 'roulette_bets' not in player_data or not isinstance(player_data.get('roulette_bets'), dict):
            player_data['roulette_bets'] = {}
            
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


# --- Legacy/Compatibility Functions ---
# These delegate to the singleton instance for backward compatibility

def load_boom_count() -> int:
    """Legacy function - delegates to DataManager singleton."""
    return get_data_manager().load_boom_count()

def save_boom_count():
    """Legacy function - delegates to DataManager singleton."""
    get_data_manager().save_boom_count()

def get_boom_count() -> int:
    """Legacy function - delegates to DataManager singleton."""
    return get_data_manager().get_boom_count()

def load_answers() -> dict[str, int]:
    """Legacy function - delegates to DataManager singleton."""
    return get_data_manager().load_answers()

def save_answers():
    """Legacy function - delegates to DataManager singleton."""
    get_data_manager().save_answers()

def get_answers() -> dict[str, int]:
    """Legacy function - delegates to DataManager singleton."""
    return get_data_manager().get_answers()

def update_answer(key: str, value: int):
    """Legacy function - delegates to DataManager singleton."""
    get_data_manager().update_answer(key, value)

def get_data_manager():
    """Returns a singleton instance of the data manager."""
    return DataManager()

# Initialize the singleton on module import
_data_manager = get_data_manager()
