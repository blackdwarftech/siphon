from livekit.agents import WorkerOptions, cli, WorkerType, JobExecutorType
from functools import partial
from typing import Any, Optional, Dict
import sys

from .core.entrypoint import entrypoint


class Agent:
    def __init__(
        self,
        agent_name: Optional[str] = None,
        llm: Optional[Dict[str, Any]] = None,
        stt: Optional[Dict[str, Any]] = None,
        tts: Optional[Dict[str, Any]] = None,
        send_greeting: Optional[bool] = True,
        greeting_instructions: Optional[str] = "Greet and introduce yourself briefly",
        system_instructions: Optional[str] = "You are a helpful voice assistant",
        allow_interruptions: Optional[bool] = True,
        min_silence_duration: Optional[float] = 0.25,
        activation_threshold: Optional[float] = 0.55,
        prefix_padding_duration: Optional[float] = 0.25,
        min_endpointing_delay: Optional[float] = 0.45,
        max_endpointing_delay: Optional[float] = 0.9,
        min_interruption_duration: Optional[float] = 0.08,
        tools: Optional[list[Any]] = None
    ) -> None:
        self._default_agent_name = agent_name

        self.llm = llm
        self.tts = tts
        self.stt = stt

        self.send_greeting = send_greeting
        self.greeting_instructions = greeting_instructions
        self.system_instructions = system_instructions

        self.allow_interruptions = allow_interruptions

        self.min_silence_duration = min_silence_duration
        self.activation_threshold = activation_threshold
        self.prefix_padding_duration = prefix_padding_duration
        self.min_endpointing_delay = min_endpointing_delay
        self.max_endpointing_delay = max_endpointing_delay
        self.min_interruption_duration = min_interruption_duration
        
        self.tools = tools or []

        self.entrypoint = partial(
            entrypoint,
            llm=self.llm,
            tts=self.tts,
            stt=self.stt,
            send_greeting=self.send_greeting,
            greeting_instructions=self.greeting_instructions,
            system_instructions=self.system_instructions,
            allow_interruptions=self.allow_interruptions,
            min_silence_duration=self.min_silence_duration,
            activation_threshold=self.activation_threshold,
            prefix_padding_duration=self.prefix_padding_duration,
            min_endpointing_delay=self.min_endpointing_delay,
            max_endpointing_delay=self.max_endpointing_delay,
            min_interruption_duration=self.min_interruption_duration,
            tools=self.tools,
        )

    def _run(self, agent_name: Optional[str], mode: str) -> None:
        name = agent_name or self._default_agent_name
        if not name:
            raise ValueError("agent_name must be provided either when constructing Agent or when calling dev/start/download_files")

        original_argv = sys.argv.copy()
        try:
            sys.argv = [sys.argv[0], mode]

            cli.run_app(
                WorkerOptions(
                    entrypoint_fnc=self.entrypoint,
                    agent_name=name,
                    worker_type=WorkerType.ROOM,
                    job_executor_type=JobExecutorType.PROCESS,
                    job_memory_warn_mb=700,
                    job_memory_limit_mb=1000,
                )
            )
        finally:
            sys.argv = original_argv

    def dev(self, agent_name: Optional[str] = None) -> None:
        try:
            self._run(agent_name=agent_name, mode="dev")
        except Exception:
            self.download_files(agent_name)
            self._run(agent_name=agent_name, mode="dev")

    def start(self, agent_name: Optional[str] = None) -> None:
        try:
            self._run(agent_name=agent_name, mode="start")
        except Exception:
            self.download_files(agent_name)
            self._run(agent_name=agent_name, mode="start")

    def download_files(self, agent_name: Optional[str] = None) -> None:
        self._run(agent_name=agent_name, mode="download-files")
            

    


