"""
IntelligentInterruptSession - A custom AgentSession with smart interrupt handling.

The interrupt logic (ignoring filler words like "yeah", "ok") is now handled
directly in the livekit-agents AgentActivity class via the _is_ignorable_transcript
method. This module provides a convenient wrapper class for use in your agents.

Usage:
    from modular import IntelligentInterruptSession
    
    session = IntelligentInterruptSession(
        vad=silero.VAD.load(),
        stt=your_stt,
        llm=your_llm,
        tts=your_tts,
    )
"""

from livekit.agents import AgentSession


class IntelligentInterruptSession(AgentSession):
    """
    Custom AgentSession with intelligent interrupt handling.
    
    This session automatically ignores filler words ('yeah', 'ok', 'hmm') 
    while still responding to explicit interrupt commands ('stop', 'wait', 'no').
    
    The logic is implemented in the underlying AgentActivity class's
    _is_ignorable_transcript method.
    """
    pass  # All interrupt logic is now in AgentActivity._is_ignorable_transcript