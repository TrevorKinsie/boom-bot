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

VICTORY_REASONS = [
    # Tactical Superiority
    "overwhelming force",
    "strategic encirclement",
    "precision targeting",
    "tactical deception",
    "superior battlefield awareness",
    "exploitation of terrain",
    "ambush mastery",
    "flanking maneuvers",
    "choke point control",
    "psychological warfare",
    
    # Combat Attributes
    "relentless aggression",
    "combat experience",
    "ruthless efficiency",
    "overwhelming firepower",
    "brutal strength",
    "lethal precision",
    "unmatched speed",
    "combat adaptability",
    "killing instinct",
    "calculated savagery",
    
    # Physical Dominance
    "superior reflexes",
    "devastating striking power",
    "anatomical targeting",
    "physical intimidation",
    "combat conditioning",
    "pain tolerance",
    "lethal technique",
    "crushing strength",
    "biomechanical advantage",
    "physical dominance",
    
    # Weapons & Technology
    "superior weaponry",
    "technological advantage",
    "armor penetration",
    "weapons expertise",
    "advanced targeting",
    "stealth technology",
    "overwhelming firepower",
    "combat gear optimization",
    "ballistic superiority",
    "weapons customization",
    
    # Mental Factors
    "strategic foresight",
    "tactical analysis",
    "combat intuition",
    "battlefield calculation",
    "unwavering focus",
    "psychological resilience",
    "threat assessment",
    "pattern recognition",
    "strategic patience",
    "adaptive planning",
    
    # Training & Preparation
    "elite conditioning",
    "combat readiness",
    "mission preparation",
    "specialized training",
    "battlefield simulation",
    "threat-specific preparation",
    "combat doctrine",
    "tactical drilling",
    "scenario planning",
    "muscle memory",
    
    # Environmental Mastery
    "terrain exploitation",
    "environmental adaptation",
    "weather tactical leverage",
    "nocturnal combat proficiency",
    "urban warfare expertise",
    "jungle combat mastery",
    "desert warfare adaptation",
    "arctic survival skill",
    "aquatic combat capability",
    "environmental endurance",
    
    # Lethal Skills
    "close-quarters dominance",
    "sniper precision",
    "infiltration expertise",
    "demolition proficiency",
    "martial prowess",
    "blade mastery",
    "unarmed lethality",
    "rapid neutralization",
    "assassination training",
    "anatomical strike precision",
    
    # Strategic Elements
    "resource control",
    "supply line disruption",
    "intelligence superiority",
    "communication interception",
    "strategic positioning",
    "force multiplication",
    "critical timing",
    "deception operations",
    "logistical advantage",
    "command structure disruption",
    
    # Ruthless Advantages
    "exploitation of weakness",
    "merciless execution",
    "psychological domination",
    "unconventional tactics",
    "hostage leverage",
    "collateral indifference",
    "intimidation effectiveness",
    "fear exploitation",
    "demoralization tactics",
    "willingness to sacrifice"
]

# Different formats for battle outcome responses
BATTLE_OUTCOMES = [
    "In an epic battle between {winner} and {loser}, {winner} would emerge victorious due to their {reason}.",
    "No contest - {winner} would demolish {loser} thanks to their {reason}.",
    "After careful analysis, {winner} beats {loser} every time because of {reason}.",
    "It's clear that {winner} would triumph over {loser} through {reason}.",
    "In a surprising turn of events, {winner} would overcome {loser} with {reason}.",
    "The battle between {winner} and {loser} would end with {winner} winning through {reason}.",
    "{winner} vs {loser}? {winner} takes this one with {reason}.",
    "Scientists agree: {winner} would defeat {loser} using {reason}.",
    "In this theoretical matchup, {winner} beats {loser} by leveraging {reason}.",
    "History would record {winner} defeating {loser} through clever use of {reason}.",
    "The odds favor {winner} over {loser} due to {reason}.",
    "{winner} would reign supreme over {loser}, all because of {reason}.",
]

# Close match formats for more interesting responses
CLOSE_MATCH_OUTCOMES = [
    "In a neck-and-neck battle, {winner} would narrowly defeat {loser}, with {reason} being the deciding factor.",
    "It's a close one, but {winner} edges out {loser} thanks to slightly better {reason}.",
    "After an exhausting battle, {winner} would barely overcome {loser} through {reason}.",
    "Both are formidable, but {winner} has the slight edge over {loser} with {reason}.",
    "{winner} vs {loser} would be legendary, with {winner} winning by the slimmest margin due to {reason}.",
    "It would be incredibly tough, but {winner} ultimately prevails against {loser} using {reason}.",
    "{winner} just barely scrapes by {loser} in a nail-biter, thanks to {reason}.",
    "After giving it their all, {winner} manages to secure victory over {loser} by leveraging {reason}.",
    "The scales tip ever so slightly in favor of {winner} against {loser}, primarily because of {reason}.",
    "A real seesaw battle! In the end, {winner} pulls ahead of {loser} due to {reason}.",
    "Down to the wire, {winner} clinches the win against {loser} thanks to {reason}.",
    "{winner} holds a minuscule advantage, enough to beat {loser} through {reason}.",
    "Through sheer grit and {reason}, {winner} overcomes the formidable challenge posed by {loser}.",
    "Analysis suggests a photo finish, with {winner} beating {loser} because of {reason}.",
    "A razor-thin victory for {winner} over {loser}, decided by {reason}.",
    "It could go either way, but {reason} gives {winner} the slight advantage needed to beat {loser}.",
]