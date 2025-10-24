"""
Profanity filter utility for filtering inappropriate content in student submissions.
"""
import re

# Comprehensive list of profane words and variations
PROFANITY_LIST = {
    # English profanity
    'fuck', 'fucking', 'fucker', 'fucked', 'fucks', 'fuk', 'fck', 'fuck', 'fuckk',
    'shit', 'shitty', 'shitter', 'shits', 'sh1t', 'sht', 'shitt',
    'bitch', 'bitches', 'bitching', 'b*tch', 'b1tch',
    'bastard', 'bastards', 'bstrd',
    'ass', 'asshole', 'arse', 'arsehole', 'a$$', 'a**hole',
    'damn', 'damned', 'dammit',
    'hell', 'hells',
    'cunt', 'cunt',
    'dick', 'dicks', 'dick',
    'cock', 'cocks', 'cock',
    'pussy', 'pussies', 'pussy',
    'whore', 'whore',
    'slut', 'sluts', 'slut',
    'piss', 'pissed', 'p*ss',
    'nigger', 'nigga', 'nigger', 'nigga',
    'fag', 'faggot', 'fag', 'faggot',
    'retard', 'retarded', 'retard',
    'motherfucker', 'mofo', 'mf', 'motherf*cker',
    'sex', 'sexy', 'sexual',
    'rape', 'raping', 'raped',
    'nazi', 'hitler',
    'porn', 'porno', 'pornography',
    
    # Common leetspeak and obfuscations
    'fvck', 'phuck', 'sh!t', 'b!tch', '@ss', 'a55',
    'd1ck', 'c0ck', 'pu$$y', 'wh0re', '5hit',
    
    # Filipino/Tagalog profanity
    'putang', 'putangina', 'puta', 'tangina', 'tanginamo',
    'gago', 'gaga', 'bobo', 'tanga', 'tarantado',
    'ulol', 'yawa', 'pakyu', 'pakyo',
    'letse', 'kupal',
    'gunggong',
    'kantot', 'kantutan', 'tamod', 'titi', 'bilat', 'puke',
    'burat', 'bayag', 'jakol',
    
    # Common variations and misspellings
    'fucc', 'fuk', 'phuq', 'phuc',
}

def contains_profanity(text):
    """
    Check if text contains profanity.
    
    Args:
        text (str): Text to check
        
    Returns:
        tuple: (bool, list) - (contains_profanity, list of found profane words)
    """
    if not text:
        return False, []
    
    # Convert to lowercase for checking
    text_lower = text.lower()
    
    # Remove special characters but keep spaces for word boundary detection
    # This helps catch obfuscated profanity like "f.u.c.k" or "f-u-c-k"
    cleaned_text = re.sub(r'[^a-z0-9\s]', '', text_lower)
    
    found_profanity = []
    
    # Check each word in the profanity list
    for profane_word in PROFANITY_LIST:
        # Use word boundaries to avoid false positives
        # For example, "assessment" shouldn't trigger "ass"
        pattern = r'\b' + re.escape(profane_word) + r'\b'
        
        # Also check in the cleaned text (without special chars)
        if re.search(pattern, text_lower) or re.search(pattern, cleaned_text):
            found_profanity.append(profane_word)
            continue
        
        # Check for the word with spaces between letters (e.g., "f u c k")
        spaced_pattern = r'\b' + r'\s*'.join(re.escape(char) for char in profane_word) + r'\b'
        if re.search(spaced_pattern, text_lower):
            found_profanity.append(profane_word)
    
    return len(found_profanity) > 0, found_profanity


def filter_profanity(text, replacement='***'):
    """
    Replace profanity in text with asterisks or custom replacement.
    
    Args:
        text (str): Text to filter
        replacement (str): Replacement string for profanity (default: '***')
        
    Returns:
        str: Filtered text
    """
    if not text:
        return text
    
    filtered_text = text
    text_lower = text.lower()
    
    for profane_word in PROFANITY_LIST:
        # Case-insensitive replacement while preserving original case structure
        pattern = re.compile(re.escape(profane_word), re.IGNORECASE)
        filtered_text = pattern.sub(replacement, filtered_text)
        
        # Also handle spaced versions
        spaced_pattern = r'\s*'.join(re.escape(char) for char in profane_word)
        spaced_regex = re.compile(spaced_pattern, re.IGNORECASE)
        filtered_text = spaced_regex.sub(replacement, filtered_text)
    
    return filtered_text


def validate_text(text):
    """
    Validate text for profanity and return validation result.
    
    Args:
        text (str): Text to validate
        
    Returns:
        dict: Validation result with keys 'valid', 'message', 'found_words'
    """
    contains_prof, found_words = contains_profanity(text)
    
    if contains_prof:
        return {
            'valid': False,
            'message': 'Your submission contains inappropriate language. Please remove profane words and try again.',
            'found_words': found_words
        }
    
    return {
        'valid': True,
        'message': 'Text is appropriate.',
        'found_words': []
    }
