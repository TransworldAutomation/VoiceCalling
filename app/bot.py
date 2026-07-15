"""
The Pipecat voice pipeline (Layer 2) — written for Pipecat 1.5.

This is the "brain + ears + mouth" of a single phone call:

   caller's voice  ->  Sarvam STT  ->  Claude (interview logic)  ->  Sarvam TTS  ->  caller

Sarvam's saaras STT model AUTO-DETECTS the caller's language, so the person can
answer in Hindi, Marathi, Tamil, English, etc. and it still understands. Claude
runs the interview; Sarvam speaks the questions in the language you set in config.

Every turn of the conversation is saved to the database so the transcript and
summary appear in the dashboard.
"""

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    EndFrame,
    LLMRunFrame,
    TranscriptionFrame,
    TTSTextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from app import config, database


class TranscriptLogger(FrameProcessor):
    """Passes frames through untouched, but records what was said to the DB.

    A FrameProcessor can only be placed in a pipeline once, so we create one
    logger for the caller's speech and another for the AI's speech.
    """

    def __init__(self, call_id: int, role: str):
        super().__init__()
        self._call_id = call_id
        self._role = role  # 'user' (caller) or 'agent' (AI)

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if self._role == "user" and isinstance(frame, TranscriptionFrame) and frame.text:
            database.add_message(self._call_id, "user", frame.text)
        elif self._role == "agent" and isinstance(frame, TTSTextFrame) and frame.text:
            database.add_message(self._call_id, "agent", frame.text)
        await self.push_frame(frame, direction)


async def run_bot(websocket, stream_sid: str, call_sid: str, call_id: int):
    """Build and run the interview pipeline for one connected call."""

    # Read THIS call's details: the note (the question to ask) and the language,
    # both coming from the contact's row in your Excel.
    call_row = database.get_call(call_id) or {}
    # The question(s) the AI asks: a contact-specific note wins; otherwise the
    # global question box saved on the dashboard; otherwise the default interview.
    note = call_row.get("note")
    if not (note and note.strip()):
        note = database.get_setting("interview_script") or config.DEFAULT_QUESTION
    call_language = config.normalize_language(
        call_row.get("language") or config.DEFAULT_LANGUAGE
    )

    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=config.TWILIO_ACCOUNT_SID,
        auth_token=config.TWILIO_AUTH_TOKEN,
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_sample_rate=8000,   # Twilio phone audio is 8kHz; match it end-to-end
            add_wav_header=False,
            # stop_secs=0.5: respond ~0.3s sooner after the caller stops talking.
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.5)),
            serializer=serializer,
        ),
    )

    # saaras:v3 auto-detects the spoken language (leave language unset).
    stt = SarvamSTTService(
        api_key=config.SARVAM_API_KEY,
        settings=SarvamSTTService.Settings(model=config.SARVAM_STT_MODEL),
    )

    tts = SarvamTTSService(
        api_key=config.SARVAM_API_KEY,
        sample_rate=8000,  # generate at Twilio's phone rate (no garbling resample)
        settings=SarvamTTSService.Settings(
            model=config.SARVAM_TTS_MODEL,
            voice=config.SARVAM_TTS_VOICE,
            language=call_language,
        ),
    )

    llm = AnthropicLLMService(
        api_key=config.ANTHROPIC_API_KEY,
        settings=AnthropicLLMService.Settings(model=config.LLM_MODEL_REALTIME),
    )

    # Universal conversation memory, seeded with the interview instructions.
    # If this call has a note, the AI asks ONLY that question (in call_language).
    context = LLMContext(
        messages=[{
            "role": "system",
            "content": config.build_system_prompt(custom_question=note, language=call_language),
        }]
    )
    aggregators = LLMContextAggregatorPair(context)

    log_user = TranscriptLogger(call_id, role="user")
    log_agent = TranscriptLogger(call_id, role="agent")

    pipeline = Pipeline([
        transport.input(),        # audio in from the caller
        stt,                      # speech -> text (auto-detects language)
        log_user,                 # save what the person said
        aggregators.user(),       # add it to conversation memory
        llm,                      # Claude decides the next line
        tts,                      # text -> speech
        log_agent,                # save what the AI said
        transport.output(),       # audio out to the caller
        aggregators.assistant(),  # record the AI's turn in memory
    ])

    # allow_interruptions=False: on a phone line the caller's handset echoes the
    # AI's own voice back into the mic; with interruptions on, that echo was
    # cutting the AI off after one word AND creating malformed context messages
    # that crashed the LLM ('role' error). Off = the AI finishes each sentence.
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=False),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the interview: tell Claude to greet and ask the first question.
        context.add_message({
            "role": "user",
            "content": "The call just connected. Greet the person warmly and ask your first question.",
        })
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.queue_frames([EndFrame()])

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
