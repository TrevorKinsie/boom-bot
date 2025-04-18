import logging
import random
from inflect import engine
from telegram import Update
from telegram.ext import ContextTypes

# Import replies
from replies import (
    SASSY_REPLIES_HIGH,
    SASSY_REPLIES_LOW,
    SASSY_REPLIES_INVALID,
    QUESTION_REPLY_VARIATIONS,
    PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS,
    SASSY_REPLIES_WHAT
)

# Import data management functions
import data_manager

# Import NLTK utility functions
from nltk_utils import normalize_question_nltk, normalize_question_simple, extract_subject

logger = logging.getLogger(__name__)
p = engine() # Initialize inflect engine

# --- Command Handlers ---

async def boom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /boom command (simple booms or sassy replies)."""
    boom_count = random.randint(1, 5)  # Default to random if no valid number is given

    if context.args:  # Check if any arguments were passed with the command
        try:
            requested_count = int(context.args[0])
            if 1 <= requested_count <= 5:
                boom_count = requested_count
            elif requested_count > 5:
                reply = random.choice(SASSY_REPLIES_HIGH)
                await update.message.reply_text(reply)
                return
            else:  # requested_count < 1
                reply = random.choice(SASSY_REPLIES_LOW)
                await update.message.reply_text(reply)
                return

        except (IndexError, ValueError):
            reply = random.choice(SASSY_REPLIES_INVALID)
            await update.message.reply_text(reply)
            return

    # If we reach here, args were valid or absent
    booms = "💥" * boom_count
    await update.message.reply_text(booms)


async def _process_howmanybooms(update: Update, question_content: str) -> None:
    """Processes the extracted question, finds/generates booms, and replies.
       Uses NLTK for fuzzy matching and subject extraction. Handles pluralization and capitalization.
    """
    question_answers = data_manager.get_answers() # Get current answers
    incoming_words = normalize_question_nltk(question_content)
    logger.info(f"Normalized incoming question '{question_content}' to words: {incoming_words}")

    match_found = False
    matched_question_key = None
    highest_similarity = 0.0
    similarity_threshold = 0.7  # Adjust this threshold (0.0 to 1.0) as needed

    # Only attempt matching if normalization yielded significant words
    if incoming_words:
        # Compare against stored questions
        for stored_key, stored_count in question_answers.items():
            stored_words = normalize_question_nltk(stored_key)
            if not stored_words:
                continue  # Skip empty stored questions

            # Calculate Jaccard similarity
            intersection = len(incoming_words.intersection(stored_words))
            union = len(incoming_words.union(stored_words))
            similarity = intersection / union if union > 0 else 0

            logger.debug(f"Comparing incoming {incoming_words} with stored '{stored_key}' ({stored_words}). Similarity: {similarity:.2f}")

            # Check if this is the best match so far above the threshold
            if similarity >= similarity_threshold and similarity > highest_similarity:
                highest_similarity = similarity
                matched_question_key = stored_key
                match_found = True
    elif not question_content.strip(): # Normalization empty AND original input was empty/whitespace
        logger.warning(f"Question content was empty or whitespace.")
        reply = random.choice(SASSY_REPLIES_WHAT)
        await update.message.reply_text(reply)
        return
    # If incoming_words is empty but question_content was not, proceed to treat as new below

    # Extract subject *after* finding potential match or deciding it's new
    # Use original content for subject extraction if normalization failed but input existed
    subject_base = question_content if not incoming_words else question_content # Or adjust logic as needed
    extracted_subject = extract_subject(subject_base)

    reply_text = "" # Initialize reply_text
    subject_to_use = extracted_subject # Default to non-capitalized

    if match_found and matched_question_key:
        # Found a sufficiently similar question
        count = question_answers[matched_question_key]
        count_str = p.no("BOOM", count)
        reply_format = random.choice(PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS)

        # Capitalize subject only if the chosen reply format starts with it
        if reply_format.startswith("{subject}"):
            subject_to_use = extracted_subject.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_to_use)
        logger.info(f"Found similar question '{matched_question_key}' (Similarity: {highest_similarity:.2f}) for '{question_content}'. Answer: {count} booms")

    else: # No similar question found OR normalization yielded nothing but input was present
        # No similar question found, treat as new
        storage_key = normalize_question_simple(question_content)

        if not storage_key: # This check might be redundant now but kept for safety
            logger.warning(f"Original question '{question_content}' also resulted in empty simple normalized key.")
            reply = random.choice(SASSY_REPLIES_WHAT)
            await update.message.reply_text(reply)
            return

        if not incoming_words:
             logger.info(f"No significant words after NLTK normalization for '{question_content}', but treating as new question with key '{storage_key}'.")
        else:
             logger.info(f"No similar question found for '{question_content}'. Treating as new question with key '{storage_key}'.")

        question_boom_count = random.randint(1, 5)
        count_str = p.no("BOOM", question_boom_count)
        reply_format = random.choice(QUESTION_REPLY_VARIATIONS)

        # Capitalize subject only if the chosen reply format starts with it
        if reply_format.startswith("{subject}"):
            subject_to_use = extracted_subject.capitalize()

        # Use the potentially capitalized subject and pluralized count string for the reply
        reply_text = reply_format.format(count_str=count_str, subject=subject_to_use)
        data_manager.update_answer(storage_key, question_boom_count) # Update answers dict
        data_manager.save_answers() # Save updated answers

    # Send the final reply
    await update.message.reply_text(reply_text)


async def booms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /howmanybooms command (text-based)."""
    if context.args:
        question_content = " ".join(context.args)
        logger.info(f"Processing question from text args: '{question_content}'")
        await _process_howmanybooms(update, question_content)
    else:
        # No arguments provided with the text command
        reply = random.choice(SASSY_REPLIES_WHAT)
        await update.message.reply_text(reply)


async def handle_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photo messages with captions containing /howmanybooms."""
    # Filters ensure message and caption exist
    caption = update.message.caption
    command_name = "/howmanybooms"
    # Find command case-insensitively
    command_pos = caption.lower().find(command_name)

    if command_pos != -1:
        # Extract text after the command
        question_content = caption[command_pos + len(command_name):].strip()
        logger.info(f"Processing question from photo caption: '{question_content}'")

        if question_content:
            await _process_howmanybooms(update, question_content)
        else:
            # Command was in caption, but no text followed it
            reply = random.choice(SASSY_REPLIES_WHAT)
            await update.message.reply_text(reply)
    # else: command not found in caption, do nothing for this handler
