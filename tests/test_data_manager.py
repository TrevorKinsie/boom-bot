# test_data_manager.py
import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from collections import defaultdict

# Add parent directory to sys.path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module itself to access its globals correctly
import data_manager

# Import functions to test
from data_manager import (
    get_answers, load_boom_count, load_answers,
    save_boom_count, save_answers, update_answer,
    BOOM_COUNT_FILE, ANSWERS_FILE, GAME_DATA_FILE, DataManager
    # Removed boom_count, question_answers from direct import
)

@pytest.fixture(autouse=True)
def reset_globals():
    """Resets global variables in the data_manager module before each test."""
    # Modify globals via the module
    data_manager.boom_count = 0
    data_manager.question_answers = {}
    # Clean up files if they exist from previous failed tests
    for f in [BOOM_COUNT_FILE, ANSWERS_FILE, GAME_DATA_FILE]:
        if os.path.exists(f):
            os.remove(f)
    yield # Run the test
    # Clean up files after test
    for f in [BOOM_COUNT_FILE, ANSWERS_FILE, GAME_DATA_FILE]:
        if os.path.exists(f):
            os.remove(f)

# --- Boom Count Tests ---

def test_load_boom_count_file_exists():
    # Arrange
    expected_count = 42
    with open(BOOM_COUNT_FILE, 'w') as f:
        json.dump({"boom_count": expected_count}, f)

    # Act
    loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == expected_count

def test_load_boom_count_file_not_found():
    # Arrange (file doesn't exist)

    # Act
    loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == 0 # Default value
    assert data_manager.boom_count == 0 # Global should be default

def test_load_boom_count_invalid_json():
    # Arrange
    with open(BOOM_COUNT_FILE, 'w') as f:
        f.write("invalid json")

    # Act
    loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == 0 # Default value on error
    assert data_manager.boom_count == 0 # Global should be default

def test_save_boom_count():
    # Arrange
    # Modify global via the module
    data_manager.load_boom_count() # Ensure global is loaded before modification
    data_manager.boom_count = 55

    # Act
    data_manager.save_boom_count()

    # Assert
    assert os.path.exists(BOOM_COUNT_FILE)
    # Reload the count from the file to verify save
    reloaded_count = data_manager.load_boom_count()
    assert reloaded_count == 55
    # Verify file content directly as well
    with open(BOOM_COUNT_FILE, 'r') as f:
        data = json.load(f)
        assert data == {"boom_count": 55}

def test_get_boom_count():
    # Arrange
    # Modify global via the module
    data_manager.boom_count = 99
    # Act & Assert
    # Access the global variable via the module
    assert data_manager.boom_count == 99

# --- Question/Answer Tests ---

def test_load_answers_file_exists():
    # Arrange
    expected_answers = {"q1": "a1", "q2": "a2"}
    with open(ANSWERS_FILE, 'w') as f:
        json.dump(expected_answers, f, indent=4)

    # Act
    loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == expected_answers
    # Check global via the module
    assert data_manager.question_answers == expected_answers

def test_load_answers_file_not_found():
    # Arrange (file doesn't exist)

    # Act
    loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == {} # Default value
    assert data_manager.question_answers == {} # Global default

def test_load_answers_invalid_json():
    # Arrange
    with open(ANSWERS_FILE, 'w') as f:
        f.write("invalid json")

    # Act
    loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == {} # Default on error
    assert data_manager.question_answers == {} # Global default

def test_save_answers():
    # Arrange
    # Modify global via the module
    data_manager.load_answers() # Ensure global is loaded before modification
    data_manager.question_answers = {"hello": "world", "test": "data"}

    # Act
    data_manager.save_answers()

    # Assert
    assert os.path.exists(ANSWERS_FILE)
    # Reload answers from file to verify save
    reloaded_answers = data_manager.load_answers()
    assert reloaded_answers == {"hello": "world", "test": "data"}
    # Verify file content directly
    with open(ANSWERS_FILE, 'r') as f:
        data = json.load(f)
        assert data == {"hello": "world", "test": "data"}

def test_get_answer_exists():
    # Arrange
    # Modify global via the module
    data_manager.question_answers = {"ping": "pong"}
    # Act & Assert
    # Call the function normally
    assert data_manager.get_answers().get("ping") == "pong"

def test_get_answer_not_exists():
    # Arrange
    # Modify global via the module
    data_manager.question_answers = {"ping": "pong"}
    # Act & Assert
    assert data_manager.get_answers().get("ding") is None

def test_add_answer():
    # Arrange
    # Modify global via the module
    data_manager.load_answers() # Ensure global is loaded before modification
    data_manager.question_answers = {"initial": "value"}
    # Mock save_answers to avoid file I/O
    # Patch the function in the module where it's defined
    with patch('data_manager.save_answers') as mock_save:
        # Act
        data_manager.update_answer("new_q", "new_a")
        # Assert
        # Check the global variable state via the module
        assert data_manager.question_answers == {"initial": "value", "new_q": "new_a"}
        mock_save.assert_called_once()

# --- Game Data Tests ---

@pytest.fixture
def mock_data_manager(tmp_path):
    """Provides a DataManager instance using a temporary file."""
    temp_file = tmp_path / "test_game_data.json"
    manager = DataManager(data_file=temp_file)
    # Ensure data is clean before each test using this fixture
    manager.data = manager._load_data() # Reload to reset
    yield manager
    # Clean up the temp file after test if needed, though tmp_path handles it

def test_load_game_data_file_exists(mock_data_manager, tmp_path):
    # Arrange
    game_data = {
        "12345": {'channel_state': {'craps_state': 2, 'craps_point': 6}, 'players': {'1': {'balance': '100.00', 'craps_bets': {}}}},
        "67890": {'channel_state': {'craps_state': 1, 'craps_point': None}, 'players': {'2': {'balance': '50.00', 'craps_bets': {}}}}
    }
    # Save data using the manager's internal method for setup
    mock_data_manager.data = defaultdict(lambda: {'channel_state': {}, 'players': defaultdict(dict)}, game_data)
    mock_data_manager._save_data()

    # Act: Create a new instance to force loading from the file
    new_manager = DataManager(data_file=mock_data_manager.data_file)
    loaded_data = new_manager.data # Access the loaded data

    # Assert
    # Check that the raw data is loaded correctly (defaultdict converted for comparison)
    assert json.loads(json.dumps(loaded_data)) == game_data

def test_load_game_data_file_not_found(tmp_path):
    # Arrange: Use a path that doesn't exist
    non_existent_file = tmp_path / "non_existent.json"
    manager = DataManager(data_file=non_existent_file)

    # Act
    loaded_data = manager.data

    # Assert
    assert loaded_data == {} # Default value is an empty defaultdict

def test_load_game_data_invalid_json(tmp_path):
    # Arrange
    invalid_file = tmp_path / "invalid.json"
    with open(invalid_file, 'w') as f:
        f.write("invalid json")
    manager = DataManager(data_file=invalid_file)

    # Act
    loaded_data = manager.data

    # Assert
    assert loaded_data == {} # Default on error

def test_save_game_data(mock_data_manager):
    # Arrange
    channel_id1 = "111"
    channel_id2 = "222"
    user_id1 = "1"
    user_id2 = "2"

    data1 = {'balance': '90.00', 'craps_bets': {'pass': '10'}}
    data2 = {'balance': '110.00', 'craps_bets': {}}
    channel_data1 = {'craps_state': 2}

    # Act: Use manager methods to save data
    mock_data_manager.save_player_data(channel_id1, user_id1, data1)
    mock_data_manager.save_player_data(channel_id2, user_id2, data2)
    mock_data_manager.save_channel_data(channel_id1, channel_data1)

    # Assert: Check the existence of the manager's specific data file
    assert mock_data_manager.data_file.exists()
    with open(mock_data_manager.data_file, 'r') as f:
        saved_data = json.load(f)
        expected_data = {
            channel_id1: {
                'channel_state': channel_data1,
                'players': {user_id1: data1}
            },
            channel_id2: {
                'channel_state': {}, # Default channel state
                'players': {user_id2: data2}
            }
        }
        assert saved_data == expected_data

def test_save_game_data_empty(mock_data_manager):
    # Arrange: Manager starts empty
    # Act: Save the initial empty state
    mock_data_manager._save_data()

    # Assert
    assert mock_data_manager.data_file.exists()
    with open(mock_data_manager.data_file, 'r') as f:
        saved_data = json.load(f)
        assert saved_data == {}

# Add tests for new DataManager methods
def test_get_channel_data(mock_data_manager):
    channel_id = "test_channel"
    data = {'state': 1, 'point': None}
    mock_data_manager.save_channel_data(channel_id, data)
    assert mock_data_manager.get_channel_data(channel_id) == data

def test_get_player_data_existing_player(mock_data_manager):
    channel_id = "test_channel"
    user_id = "existing_user"
    data = {'balance': '50.00', 'craps_bets': {'field': '5'}}
    mock_data_manager.save_player_data(channel_id, user_id, data)
    assert mock_data_manager.get_player_data(channel_id, user_id) == data

def test_get_all_players_data(mock_data_manager):
    channel_id = "test_channel"
    user1 = "user1"
    user2 = "user2"
    data1 = {'balance': '100'}
    data2 = {'balance': '200'}
    mock_data_manager.save_player_data(channel_id, user1, data1)
    mock_data_manager.save_player_data(channel_id, user2, data2)

    all_players = mock_data_manager.get_all_players_data(channel_id)
    assert all_players == {user1: data1, user2: data2}
    # Ensure it's a copy
    all_players["new_user"] = {'balance': '0'}
    assert "new_user" not in mock_data_manager.data[channel_id]['players']
