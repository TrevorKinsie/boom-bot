# test_data_manager.py
import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from collections import defaultdict
from pathlib import Path

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
    GAME_DATA_FILE, DataManager
)

@pytest.fixture(autouse=True)
def reset_globals():
    """Resets global variables in the data_manager module before each test."""
    # Modify globals via the module
    data_manager.boom_count = 0
    data_manager.question_answers = {}
    yield # Run the test

# --- Boom Count Tests ---

def test_load_boom_count_file_exists(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "boom_count.json"
    expected_count = 42
    with open(temp_boom_file, 'w') as f:
        json.dump({"boom_count": expected_count}, f)

    # Act
    with patch('data_manager.BOOM_COUNT_FILE', temp_boom_file):
        loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == expected_count

def test_load_boom_count_file_not_found(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "non_existent_boom.json"

    # Act
    with patch('data_manager.BOOM_COUNT_FILE', temp_boom_file):
        loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == 0
    assert data_manager.boom_count == 0

def test_load_boom_count_invalid_json(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "invalid_boom.json"
    with open(temp_boom_file, 'w') as f:
        f.write("invalid json")

    # Act
    with patch('data_manager.BOOM_COUNT_FILE', temp_boom_file):
        loaded_count = data_manager.load_boom_count()

    # Assert
    assert loaded_count == 0
    assert data_manager.boom_count == 0

def test_save_boom_count(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "saved_boom.json"
    with patch('data_manager.BOOM_COUNT_FILE', temp_boom_file):
        data_manager.load_boom_count()
        data_manager.boom_count = 55

        # Act
        data_manager.save_boom_count()

        # Assert
        assert os.path.exists(temp_boom_file)
        reloaded_count = data_manager.load_boom_count()
        assert reloaded_count == 55
        with open(temp_boom_file, 'r') as f:
            data = json.load(f)
            assert data == {"boom_count": 55}

def test_get_boom_count():
    # Arrange
    data_manager.boom_count = 99
    # Act & Assert
    assert data_manager.boom_count == 99

# --- Question/Answer Tests ---

def test_load_answers_file_exists(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "answers.json"
    expected_answers = {"q1": "a1", "q2": "a2"}
    with open(temp_answers_file, 'w') as f:
        json.dump(expected_answers, f, indent=4)

    # Act
    with patch('data_manager.ANSWERS_FILE', temp_answers_file):
        loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == expected_answers
    assert data_manager.question_answers == expected_answers

def test_load_answers_file_not_found(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "non_existent_answers.json"

    # Act
    with patch('data_manager.ANSWERS_FILE', temp_answers_file):
        loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == {}
    assert data_manager.question_answers == {}

def test_load_answers_invalid_json(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "invalid_answers.json"
    with open(temp_answers_file, 'w') as f:
        f.write("invalid json")

    # Act
    with patch('data_manager.ANSWERS_FILE', temp_answers_file):
        loaded_data = data_manager.load_answers()

    # Assert
    assert loaded_data == {}
    assert data_manager.question_answers == {}

def test_save_answers(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "saved_answers.json"
    with patch('data_manager.ANSWERS_FILE', temp_answers_file):
        data_manager.load_answers()
        data_manager.question_answers = {"hello": "world", "test": "data"}

        # Act
        data_manager.save_answers()

        # Assert
        assert os.path.exists(temp_answers_file)
        reloaded_answers = data_manager.load_answers()
        assert reloaded_answers == {"hello": "world", "test": "data"}
        with open(temp_answers_file, 'r') as f:
            data = json.load(f)
            assert data == {"hello": "world", "test": "data"}

def test_get_answer_exists():
    # Arrange
    data_manager.question_answers = {"ping": "pong"}
    # Act & Assert
    assert data_manager.get_answers().get("ping") == "pong"

def test_get_answer_not_exists():
    # Arrange
    data_manager.question_answers = {"ping": "pong"}
    # Act & Assert
    assert data_manager.get_answers().get("ding") is None

def test_add_answer(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "add_answers.json"
    with patch('data_manager.ANSWERS_FILE', temp_answers_file):
        data_manager.load_answers()
        data_manager.question_answers = {"initial": "value"}
        with patch('data_manager.save_answers') as mock_save:
            # Act
            data_manager.update_answer("new_q", "new_a")
            # Assert
            assert data_manager.question_answers == {"initial": "value", "new_q": "new_a"}
            mock_save.assert_called_once()

# --- Game Data Tests ---

@pytest.fixture
def mock_data_manager(tmp_path):
    """Provides a DataManager instance using a temporary file."""
    temp_file = tmp_path / "test_game_data.json"
    manager = DataManager(data_file=temp_file)
    manager.data = manager._load_data()
    yield manager

def test_load_game_data_file_exists(mock_data_manager, tmp_path):
    # Arrange
    game_data = {
        "12345": {'channel_state': {'craps_state': 2, 'craps_point': 6}, 'players': {'1': {'balance': '100.00', 'craps_bets': {}}}},
        "67890": {'channel_state': {'craps_state': 1, 'craps_point': None}, 'players': {'2': {'balance': '50.00', 'craps_bets': {}}}}
    }
    mock_data_manager.data = defaultdict(lambda: {'channel_state': {}, 'players': defaultdict(dict)}, game_data)
    mock_data_manager._save_data()

    # Act
    new_manager = DataManager(data_file=mock_data_manager.data_file)
    loaded_data = new_manager.data

    # Assert
    assert json.loads(json.dumps(loaded_data)) == game_data

def test_load_game_data_file_not_found(tmp_path):
    # Arrange
    non_existent_file = tmp_path / "non_existent.json"
    manager = DataManager(data_file=non_existent_file)

    # Act
    loaded_data = manager.data

    # Assert
    assert loaded_data == {}

def test_load_game_data_invalid_json(tmp_path):
    # Arrange
    invalid_file = tmp_path / "invalid.json"
    with open(invalid_file, 'w') as f:
        f.write("invalid json")
    manager = DataManager(data_file=invalid_file)

    # Act
    loaded_data = manager.data

    # Assert
    assert loaded_data == {}

def test_save_game_data(mock_data_manager):
    # Arrange
    channel_id1 = "111"
    channel_id2 = "222"
    user_id1 = "1"
    user_id2 = "2"

    data1 = {'balance': '90.00', 'craps_bets': {'pass': '10'}}
    data2 = {'balance': '110.00', 'craps_bets': {}}
    channel_data1 = {'craps_state': 2}

    # Act
    mock_data_manager.save_player_data(channel_id1, user_id1, data1)
    mock_data_manager.save_player_data(channel_id2, user_id2, data2)
    mock_data_manager.save_channel_data(channel_id1, channel_data1)

    # Assert
    assert mock_data_manager.data_file.exists()
    with open(mock_data_manager.data_file, 'r') as f:
        saved_data = json.load(f)
        expected_data = {
            channel_id1: {
                'channel_state': channel_data1,
                'players': {user_id1: data1}
            },
            channel_id2: {
                'channel_state': {},
                'players': {user_id2: data2}
            }
        }
        assert saved_data == expected_data

def test_save_game_data_empty(mock_data_manager):
    # Arrange
    mock_data_manager._save_data()

    # Assert
    assert mock_data_manager.data_file.exists()
    with open(mock_data_manager.data_file, 'r') as f:
        saved_data = json.load(f)
        assert saved_data == {}

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
    all_players["new_user"] = {'balance': '0'}
    assert "new_user" not in mock_data_manager.data[channel_id]['players']
