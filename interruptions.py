# interruptionfilter.py
from typing import Set, Optional

# Configurable ignore list (backchanneling words)
IGNORE_WORDS: Set[str] = {
    'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 
    'aha', 'mhm', 'sure', 'yep', 'yup', 'gotcha'
}

# Interrupt trigger words
INTERRUPT_WORDS: Set[str] = {
    'wait', 'stop', 'no', 'hold', 'pause', 'cancel'
}

def allowInterruption(transcript: str, agent_speaking: bool) -> bool:
    """
    Returns True if interruption should be allowed.
    
    Logic:
    - If agent is speaking AND transcript only contains ignore words → False
    - If transcript contains any interrupt words → True
    - If agent is silent → True (all inputs are valid)
    """
    if not transcript:
        return True
    
    transcript_lower = transcript.lower().strip()
    words = transcript_lower.split()
    
    # Check for interrupt trigger words first (highest priority)
    if any(word in INTERRUPT_WORDS for word in words):
        return True
    
    # If agent is speaking, check if ONLY backchanneling
    if agent_speaking:
        # Filter out pure backchanneling
        non_ignore_words = [w for w in words if w not in IGNORE_WORDS]
        
        # If only ignore words present, DON'T interrupt
        if len(non_ignore_words) == 0:
            return False
    
    # All other cases: allow interruption
    return True
