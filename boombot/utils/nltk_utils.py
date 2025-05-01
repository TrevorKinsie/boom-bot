import logging
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string  # Added import
import re  # Added import for regex

logger = logging.getLogger(__name__)

# Download the necessary NLTK resources
def setup_nltk():
    """Downloads required NLTK data if not present."""
    resources = ['stopwords', 'punkt', 'averaged_perceptron_tagger']
    for resource in resources:
        try:
            nltk.data.find(f"corpora/{resource}" if resource == 'stopwords' else f"tokenizers/{resource}" if resource == 'punkt' else f"taggers/{resource}")
            logger.info(f"NLTK {resource} already downloaded.")
        except LookupError:
            logger.info(f"Downloading NLTK {resource}...")
            nltk.download(resource, quiet=True)
            logger.info(f"NLTK {resource} downloaded.")

# Initialize NLTK resources at module import time
setup_nltk()

# --- Setup NLTK resources ---
stop_words = set(stopwords.words('english'))

# --- Normalization and Subject Extraction ---

def normalize_question_simple(text: str) -> str:
    """Original simple normalization for storage keys."""
    return text.lower().strip()


def normalize_question_nltk(text: str) -> set[str]:
    """Normalizes question text using NLTK for similarity comparison.
    Removes punctuation/stopwords, returns set of significant words.
    """
    if not text:  # Handle empty input early
        return set()
    try:
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        # Tokenize
        try:
            tokens = word_tokenize(text)
        except LookupError as e:
            logger.error(f"NLTK LookupError during tokenization: {e}. Falling back to simple split.")
            # Fallback: simple whitespace split if punkt fails
            tokens = text.split()

        # Remove stop words and non-alphabetic tokens
        significant_words = {word for word in tokens if word.isalpha() and word not in stop_words}
        return significant_words
    except Exception as e:
        # Catch other potential errors during normalization
        logger.error(f"Unexpected error during NLTK normalization of '{text}': {e}")
        return set()


def extract_subject(text: str) -> str:
    """Extracts the likely subject (first noun phrase) from the question text using POS tagging."""
    try:
        # Tokenize the text
        tokens = word_tokenize(text)
        # Perform Part-of-Speech tagging
        tagged_tokens = nltk.pos_tag(tokens)

        subject_words = []
        in_subject = False
        # Simple heuristic: find the first sequence of Determiner (DT), Adjective (JJ), Noun (NN/NNS/NNP/NNPS)
        for word, tag in tagged_tokens:
            # Start capturing if we see a determiner, adjective, or noun
            if tag.startswith('DT') or tag.startswith('JJ') or tag.startswith('NN'):
                subject_words.append(word)
                in_subject = True
            # Stop capturing if we are in a subject and hit something else (like a verb VB)
            elif in_subject and (tag.startswith('VB') or word in ['is', 'are', 'does', 'do', 'get', 'deserves']):
                break  # Stop after the main noun phrase, before the verb
            # If we started capturing but hit something non-essential, keep going for multi-word nouns
            elif in_subject and not (tag.startswith('DT') or tag.startswith('JJ') or tag.startswith('NN')):
                # If it's something clearly not part of the noun phrase, stop
                if word in ['?', '.'] or tag in [':', ',']:
                    break
                # Otherwise, might be part of a complex noun phrase, continue for now
                # (This part is tricky and can be refined)
                pass
            # If we haven't started capturing and it's not a starting tag, ignore
            elif not in_subject:
                continue

        # Clean up the extracted subject
        subject = " ".join(subject_words).strip()
        # Remove leading 'how many booms does/do/is/are' etc. if accidentally captured
        common_prefixes = ["how many booms does ", "how many booms do ", "how many booms is ", "how many booms are ", "how many booms "]
        for prefix in common_prefixes:
            if subject.lower().startswith(prefix):
                subject = subject[len(prefix):].strip()
                break

        # Fallback if extraction is empty or very short
        if not subject or len(subject.split()) == 0:
            logger.warning(f"Subject extraction failed for '{text}'. Falling back to full text.")
            return text.strip().rstrip('?')  # Fallback to original cleaned text

        logger.info(f"Extracted subject '{subject}' from '{text}'")
        return subject

    except LookupError as e:
        logger.error(f"NLTK LookupError during subject extraction (likely missing tagger): {e}. Falling back.")
        return text.strip().rstrip('?')  # Fallback
    except Exception as e:
        logger.error(f"Error during subject extraction for '{text}': {e}")
        return text.strip().rstrip('?')  # Fallback


def extract_contenders(text: str) -> list[str]:
    """
    Extract contenders from input like "X vs Y" or "between X and Y".
    Returns a list of contenders.
    """
    try:
        # Normalize text
        text = text.strip().lower()
        
        # Common patterns for battle comparisons
        vs_pattern = r'(.*?)\s+(?:vs\.?|versus)\s+(.*?)(?:\?|$|\.)'
        between_pattern = r'between\s+(.*?)\s+and\s+(.*?)(?:\?|$|\.)'
        or_pattern = r'(.*?)\s+or\s+(.*?)(?:\?|$|\.)'
        
        # Try each pattern
        match = re.search(vs_pattern, text)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
            
        match = re.search(between_pattern, text)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
            
        match = re.search(or_pattern, text)
        if match:
            return [match.group(1).strip(), match.group(2).strip()]
        
        # If no patterns match, try to extract noun phrases
        if not match:
            # Tokenize and tag
            tokens = word_tokenize(text)
            tagged = nltk.pos_tag(tokens)
            
            # Look for nouns and noun sequences
            contenders = []
            current_contender = []
            
            for word, tag in tagged:
                # Skip common separators and comparison words
                if word.lower() in ['vs', 'versus', 'and', 'or', 'between', 'against']:
                    if current_contender:
                        contenders.append(" ".join(current_contender))
                        current_contender = []
                    continue
                
                # Collect nouns and adjectives (for "red car" type phrases)
                if tag.startswith('NN') or tag.startswith('JJ'):
                    current_contender.append(word)
                # Close the current contender if we hit non-relevant parts
                elif current_contender:
                    contenders.append(" ".join(current_contender))
                    current_contender = []
            
            # Don't forget last contender
            if current_contender:
                contenders.append(" ".join(current_contender))
            
            # Return unique contenders (at least 2)
            unique_contenders = list(dict.fromkeys(contenders))
            if len(unique_contenders) >= 2:
                return unique_contenders
        
        # Fallback: split by common separators if we couldn't find defined contenders
        if not match:
            for sep in [' vs ', ' versus ', ' and ', ' or ', ' against ']:
                if sep in text:
                    parts = [p.strip() for p in text.split(sep) if p.strip()]
                    if len(parts) >= 2:
                        return parts
        
        # If all else fails, just return an empty list
        logger.warning(f"Could not extract contenders from '{text}'")
        return []
        
    except Exception as e:
        logger.error(f"Error extracting contenders from '{text}': {e}")
        return []
