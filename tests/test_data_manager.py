# test_data_manager.py
import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from collections import defaultdict
from pathlib import Path

# Import from the new package structure
from boombot.core.data_manager import (
    get_answers, load_boom_count, load_answers,
    save_boom_count, save_answers, update_answer,
    GAME_DATA_FILE, DataManager, get_data_manager
)

# Import the module itself to access its globals correctly
import boombot.core.data_manager as data_manager

@pytest.fixture(autouse=True)
def reset_data_manager():
    """Resets the DataManager singleton before each test."""
    # Reset the singleton instance
    DataManager.reset_instance()
    # Reset module globals for functions that might cache values
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
    with patch('boombot.core.data_manager.BOOM_COUNT_FILE', temp_boom_file):
        # Force a new instance with the patched path
        loaded_count = get_data_manager(reset=True).load_boom_count()

    # Assert
    assert loaded_count == expected_count
    assert get_data_manager().boom_count == expected_count

def test_load_boom_count_file_not_found(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "non_existent_boom.json"

    # Act
    with patch('boombot.core.data_manager.BOOM_COUNT_FILE', temp_boom_file):
        loaded_count = get_data_manager(reset=True).load_boom_count()

    # Assert
    assert loaded_count == 0
    assert get_data_manager().boom_count == 0

def test_load_boom_count_invalid_json(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "invalid_boom.json"
    with open(temp_boom_file, 'w') as f:
        f.write("invalid json")

    # Act
    with patch('boombot.core.data_manager.BOOM_COUNT_FILE', temp_boom_file):
        loaded_count = get_data_manager(reset=True).load_boom_count()

    # Assert
    assert loaded_count == 0
    assert get_data_manager().boom_count == 0

def test_save_boom_count(tmp_path):
    # Arrange
    temp_boom_file = tmp_path / "saved_boom.json"
    with patch('boombot.core.data_manager.BOOM_COUNT_FILE', temp_boom_file):
        manager = get_data_manager(reset=True)
        manager.boom_count = 55

        # Act
        manager.save_boom_count()

        # Assert
        assert os.path.exists(temp_boom_file)
        # Create new manager to verify data was correctly saved and loaded
        new_manager = get_data_manager(reset=True)
        reloaded_count = new_manager.load_boom_count()
        assert reloaded_count == 55
        with open(temp_boom_file, 'r') as f:
            data = json.load(f)
            assert data == {"boom_count": 55}

def test_get_boom_count():
    # Arrange
    manager = get_data_manager(reset=True)
    manager.boom_count = 99
    # Act & Assert
    assert manager.get_boom_count() == 99

# --- Question/Answer Tests ---

def test_load_answers_file_exists(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "answers.json"
    expected_answers = {"q1": "a1", "q2": "a2"}
    with open(temp_answers_file, 'w') as f:
        json.dump(expected_answers, f, indent=4)

    # Act
    with patch('boombot.core.data_manager.ANSWERS_FILE', temp_answers_file):
        manager = get_data_manager(reset=True)
        loaded_data = manager.load_answers()

    # Assert
    assert loaded_data == expected_answers
    assert manager.question_answers == expected_answers

def test_load_answers_file_not_found(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "non_existent_answers.json"

    # Act
    with patch('boombot.core.data_manager.ANSWERS_FILE', temp_answers_file):
        manager = get_data_manager(reset=True)
        loaded_data = manager.load_answers()

    # Assert
    assert loaded_data == {}
    assert manager.question_answers == {}

def test_load_answers_invalid_json(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "invalid_answers.json"
    with open(temp_answers_file, 'w') as f:
        f.write("invalid json")

    # Act
    with patch('boombot.core.data_manager.ANSWERS_FILE', temp_answers_file):
        manager = get_data_manager(reset=True)
        loaded_data = manager.load_answers()

    # Assert
    assert loaded_data == {}
    assert manager.question_answers == {}

def test_save_answers(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "saved_answers.json"
    with patch('boombot.core.data_manager.ANSWERS_FILE', temp_answers_file):
        manager = get_data_manager(reset=True)
        manager.question_answers = {"hello": "world", "test": "data"}

        # Act
        manager.save_answers()

        # Assert
        assert os.path.exists(temp_answers_file)
        # Create a new manager to verify data was correctly saved and loaded
        new_manager = get_data_manager(reset=True)
        reloaded_answers = new_manager.load_answers()
        assert reloaded_answers == {"hello": "world", "test": "data"}
        with open(temp_answers_file, 'r') as f:
            data = json.load(f)
            assert data == {"hello": "world", "test": "data"}

def test_get_answer_exists():
    # Arrange
    manager = get_data_manager(reset=True)
    manager.question_answers = {"ping": "pong"}
    # Act & Assert
    assert manager.get_answers().get("ping") == "pong"

def test_get_answer_not_exists():
    # Arrange
    manager = get_data_manager(reset=True)
    manager.question_answers = {"ping": "pong"}
    # Act & Assert
    assert manager.get_answers().get("ding") is None

def test_add_answer(tmp_path):
    # Arrange
    temp_answers_file = tmp_path / "add_answers.json"
    with patch('boombot.core.data_manager.ANSWERS_FILE', temp_answers_file):
        manager = get_data_manager(reset=True)
        manager.question_answers = {"initial": "value"}
        
        # Act
        manager.update_answer("new_q", "new_a")
        
        # Assert
        assert manager.question_answers == {"initial": "value", "new_q": "new_a"}
        assert os.path.exists(temp_answers_file)
        with open(temp_answers_file, 'r') as f:
            data = json.load(f)
            assert data == {"initial": "value", "new_q": "new_a"}
