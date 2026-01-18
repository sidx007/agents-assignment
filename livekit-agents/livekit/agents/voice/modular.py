from typing import TYPE_CHECKING, Literal
import asyncio
import string # Needed for the punctuation removal

# --- 1. Fix Imports ---
from livekit.agents.voice import AgentSession, AgentActivity  # <--- MUST import AgentActivity
from livekit.agents.llm import AgentHandoff
from opentelemetry import context as otel_context
from livekit.agents import llm, stt, tts, utils, vad # Ensure these are imported from livekit.agents
from livekit.agents.tokenize.basic import split_words

if TYPE_CHECKING:
    from livekit.agents import Agent

# --- 2. Fix Inheritance ---
class CustomAgentActivity(AgentActivity): # <--- CHANGED from (Agent) to (AgentActivity)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _interrupt_by_audio_activity(self) -> None:
        opt = self._session.options
        use_pause = opt.resume_false_interruption and opt.false_interruption_timeout is not None

        # 1. Server-Side Check
        if isinstance(self.llm, llm.RealtimeModel) and self.llm.capabilities.turn_detection:
            return

        # 2. THE SOLUTION: Check if we should ignore this noise
        if self.stt is not None and self._audio_recognition is not None:
            text = self._audio_recognition.current_transcript
            
            # Use helper to check for Empty Text OR Filler Words
            if self._is_ignorable_transcript(text):
                return

        # Legacy word count check
        if (
            self.stt is not None
            and opt.min_interruption_words > 0
            and self._audio_recognition is not None
        ):
            text = self._audio_recognition.current_transcript
            if len(split_words(text, split_character=True)) < opt.min_interruption_words:
                return

        # 3. Execute Interruption
        if self._rt_session is not None:
            self._rt_session.start_user_activity()

        if (
            self._current_speech is not None
            and not self._current_speech.interrupted
            and self._current_speech.allow_interruptions
        ):
            self._paused_speech = self._current_speech

            if self._false_interruption_timer:
                self._false_interruption_timer.cancel()
                self._false_interruption_timer = None

            if use_pause and self._session.output.audio and self._session.output.audio.can_pause:
                self._session.output.audio.pause()
                self._session._update_agent_state("listening")
            else:
                if self._rt_session is not None:
                    self._rt_session.interrupt()
                self._current_speech.interrupt()

    def _is_ignorable_transcript(self, text: str) -> bool:
        """
        Decides if the agent should IGNORE the user input.
        Returns True = Ignore (Agent keeps speaking).
        Returns False = Interrupt (Agent stops).
        """
        if not text or not text.strip():
            return True

        clean_text = text.lower().translate(str.maketrans("", "", string.punctuation)).strip()
        words = clean_text.split()
        
        if not words:
            return True

        interrupt_words = {"stop", "wait", "hold", "no", "cancel", "pause"}
        if any(w in interrupt_words for w in words):
            return False 

        ignored_words = {"yeah", "ok", "okay", "hmm", "aha", "right", "uh-huh", "yep", "yup"}
        return all(w in ignored_words for w in words)


class IntelligentInterruptSession(AgentSession):
    # This part was correct
    _activity: CustomAgentActivity | None = None
    _next_activity: CustomAgentActivity | None = None

    def __init__(self, *args, **kwargs):
        """Initialize the custom session."""
        super().__init__(*args, **kwargs)
    
    # This override logic was correct, just ensure imports like AgentHandoff/otel_context exist
    async def _update_activity(
        self,
        agent,
        *,
        previous_activity: Literal["close", "pause"] = "close",
        new_activity: Literal["start", "resume"] = "start",
        blocked_tasks: list[asyncio.Task] | None = None,
        wait_on_enter: bool = True,
    ) -> None:
        async with self._activity_lock:
            self._agent = agent

            if new_activity == "start":
                previous_agent = self._activity.agent if self._activity else None
                if agent._activity is not None and (
                    agent is not previous_agent or previous_activity != "close"
                ):
                    raise RuntimeError("cannot start agent: an activity is already running")

                # *** THE CRITICAL CHANGE ***
                self._next_activity = CustomAgentActivity(agent, self)
                # ***************************

            elif new_activity == "resume":
                if agent._activity is None:
                    raise RuntimeError("cannot resume agent: no existing active activity to resume")
                self._next_activity = agent._activity # type: ignore

            if self._root_span_context is not None:
                otel_context.attach(self._root_span_context)

            previous_activity_v = self._activity
            if self._activity is not None:
                if previous_activity == "close":
                    await self._activity.drain()
                    await self._activity.aclose()
                elif previous_activity == "pause":
                    await self._activity.pause(blocked_tasks=blocked_tasks or [])

            self._activity = self._next_activity
            self._next_activity = None

            run_state = self._global_run_state
            handoff_item = AgentHandoff(
                old_agent_id=previous_activity_v.agent.id if previous_activity_v else None,
                new_agent_id=self._activity.agent.id,
            )
            if run_state:
                run_state._agent_handoff(
                    item=handoff_item,
                    old_agent=previous_activity_v.agent if previous_activity_v else None,
                    new_agent=self._activity.agent,
                )
            self._chat_ctx.insert(handoff_item)

            if new_activity == "start":
                await self._activity.start()
            elif new_activity == "resume":
                await self._activity.resume()

        if wait_on_enter:
            assert self._activity._on_enter_task is not None
            await asyncio.shield(self._activity._on_enter_task)