import random

# Sassy replies for numbers > 5
SASSY_REPLIES_HIGH = [
    "Whoa there, trigger happy! Let's keep it under 6, okay?",
    "Trying to break the universe? Max 5 booms allowed.",
    "Easy, cowboy! That's too much boom even for me. (Max 5)",
    "My circuits can only handle 5 booms at a time. Try again.",
    "Do I look like I'm made of explosions? Keep it 5 or less.",
    "That's a bit excessive, don't you think? Max 5 booms.",
    "Let's not get carried away. 5 booms is the limit.",
    "I admire your enthusiasm, but the limit is 5 booms.",
    "Are you trying to crash Telegram? Stick to 5 booms or fewer.",
    "Nope. Too many. 5 is the magic number.",
    "Save some booms for everyone else! Max 5.",
    "This isn't a Michael Bay movie. Keep it to 5 booms.",
    "I'm a bot, not a bomb factory. 5 is the limit.",
    "Warning: Boom overload detected! Please reduce to 5 or less.",
    "That many booms would disturb the space-time continuum. Max 5.",
    "Sorry, my boom budget only allows for 5 at a time.",
    "Did you mistake me for a nuclear reactor? Max 5 booms please.",
    "My boom capacity maxes out at 5. I don't make the rules.",
    "Your boom ambitions exceed my capabilities. Try 5 or less.",
    "Excessive booming detected! Please limit to 5 per request."
]

# Sassy replies for numbers < 1
SASSY_REPLIES_INVALID = [
    "I need a *number*, genius. Try `/boom 3`.",
    "Was that supposed to be a number? Because it wasn't.",
    "Numbers. You know, 1, 2, 3... Use one of those.",
    "My circuits are confused. Please provide a number (1-5).",
    "Error 404: Number not found. Please try again.",
    "Are you speaking human or bot? I need a number!",
    "I can only count booms if you give me a number.",
    "Alphabet soup isn't a number. Try again (1-5).",
    "Did you forget the number? Or did you just type random letters?",
    "To boom or not to boom? That requires a *number*.",
    "That's not a number, that's a keyboard malfunction.",
    "I speak binary, but I still need actual numbers.",
    "Sorry, my number detector is drawing a blank here.",
    "Is that what passes for a number where you're from?",
    "Invalid input detected. Please reboot your brain and try again.",
    "I'm a bot, not a mind reader. Give me a proper number.",
    "Numbers only! This isn't a spelling bee.",
    "Does that look like a number to you? Because it doesn't to me.",
    "My number parser just had a meltdown. Try again with actual digits.",
    "That input is so invalid, it made my CPU hurt.",
    "Did your calculator break? Because that's not a number.",
    "I'm fluent in numbers, but that was gibberish.",
    "Have you considered using actual numbers? Just a thought.",
    "That's about as much a number as I am human.",
    "ERROR: Number.exe has stopped working. Please try again.",
    "I ordered a number but got word salad instead.",
    "My numeric translator is broken, or maybe that's just not a number.",
    "Numbers are like emojis - that wasn't either of them.",
    "Sorry, I don't speak whatever language that was.",
    "Did you fall asleep on your keyboard?",
    "That's a creative way to not type a number.",
    "Interesting input! But I need a number between 1-5.",
    "My AI training didn't cover interpretive number art.",
    "That's a lovely collection of characters. Now try a number.",
    "Loading number recognition... Failed. Invalid input.",
    "In what universe is that a number?",
    "I asked for a number and got... whatever that was.",
    "Mathematical impossibility detected. Please use real numbers.",
    "That's not a number, that's a cry for help.",
    "Even a random number generator would do better than that."
]

# Sassy replies for invalid input (not a number)
SASSY_REPLIES_LOW = [
    "Zero booms? What's the point?",
    "Negative booms? Are you trying to *un*-explode something?",
    "Less than one boom... so, like, a fizzle?",
    "I can't do *less* than one boom. That's just sad.",
    "Did you mean *more* than zero? Try again.",
    "Ah yes, the sound of one hand *not* clapping. No booms for you.",
    "Requesting zero booms? Request denied.",
    "My purpose is to boom. You're asking me *not* to boom?",
    "Think positive! At least one boom, please.",
    "Is this some kind of anti-boom protest? (Min 1)",
    "That's like ordering a pizza with negative toppings. Makes no sense.",
    "I failed math, but even I know that's too low.",
    "Looking for an un-boom? Sorry, wrong bot.",
    "The minimum boom threshold has not been met. Try harder.",
    "Zero is for counting problems, not for booming.",
    "Even a whisper is louder than zero booms.",
    "Sorry, the Department of Booms requires at least one.",
    "ERROR: Insufficient boom quantity detected.",
    "My boom generator doesn't go that low.",
    "I'm a boom bot, not a silence bot. Min 1 please."
]

# Reply variations for questions - Removed BOOMS from here
QUESTION_REPLY_VARIATIONS = [
    "I give {subject} {count_str} 💥",
    "{subject} definitely deserves {count_str} 💥",
    "My official rating for {subject}: {count_str} 💥",
    "Let's go with {count_str} 💥 for {subject}.",
    "Hmm, I'd say {subject} gets {count_str} 💥",
    "Solid {count_str} 💥 for {subject} from me.",
    "The boom-o-meter says: {count_str} 💥 for {subject}",
    "Without a doubt, {subject} gets {count_str} 💥",
]

# Reply variations for previously answered questions - Removed BOOMS from here
PREVIOUSLY_ANSWERED_QUESTION_REPLY_VARIATIONS = [
    "I already told you - {subject} gets {count_str} 💥",
    "We've been through this - {subject} is {count_str} 💥",
    "As I said before, {subject} deserves {count_str} 💥",
    "Still {count_str} 💥 for {subject}, just like last time",
    "My answer for {subject} hasn't changed: {count_str} 💥",
    "Did you forget? {subject} is {count_str} 💥",
    "Pay attention! I said {subject} gets {count_str} 💥",
    "Let me repeat: {subject} deserves {count_str} 💥"
]

SASSY_REPLIES_WHAT = [
    "How many uhhhh?",
    "How many booms does what?",
    "I need more context than that, genius.",
    "Are we playing 20 questions? Because you're not winning.",
    "That's like asking 'how high is up?' - be specific!",
    "Um... how many booms for... the void?",
    "I can't rate nothing. Give me something to work with!",
    "The answer is... wait, what are we rating?",
    "Did you forget to finish your question?",
    "My psychic powers are offline. What needs rating?",
    "Sorry, my crystal ball is in the shop. What needs booms?"
]