from livekit.agents import WorkerOptions, cli, WorkerType, JobExecutorType
from functools import partial
from typing import Any, Optional, Dict
import sys
import os

from siphon.config import get_logger
from .core.entrypoint import entrypoint

logger = get_logger("agent-runner")


class Agent:
    def __init__(
        self,
        agent_name: Optional[str] = None,
        llm: Optional[Dict[str, Any]] = None,
        stt: Optional[Dict[str, Any]] = None,
        tts: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        self._default_agent_name = agent_name

        self.llm = llm
        self.tts = tts
        self.stt = stt

        self.entrypoint_kwargs = kwargs

        self.entrypoint = partial(
            entrypoint,
            llm=self.llm,
            tts=self.tts,
            stt=self.stt,
            **self.entrypoint_kwargs
        )

    def _run(self, agent_name: Optional[str], mode: str, force_download: bool = False) -> None:
        name = agent_name or self._default_agent_name
        if not name:
            raise ValueError("agent_name must be provided either when constructing Agent or when calling dev/start/download_files")

        original_argv = sys.argv.copy()
        try:
            # WARNING: Mutating sys.argv is not thread-safe.
            # Only one Agent instance should be active per process.
            sys.argv = [sys.argv[0], mode]
            
            # Set force download environment variable if requested
            if force_download:
                os.environ["LIVEKIT_FORCE_DOWNLOAD"] = "1"

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
            # Clean up environment variable
            if force_download and "LIVEKIT_FORCE_DOWNLOAD" in os.environ:
                del os.environ["LIVEKIT_FORCE_DOWNLOAD"]

    def dev(self, agent_name: Optional[str] = None) -> None:
        try:
            self._run(agent_name=agent_name, mode="dev")
        except (FileNotFoundError, RuntimeError) as e:
            # Only retry on file/model-related errors
            logger.info(f"Initial run failed with {type(e).__name__}: {e}. Attempting to download files...")
            self.download_files(agent_name)
            self._run(agent_name=agent_name, mode="dev")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Agent dev mode failed: {e}")
            raise

    def start(self, agent_name: Optional[str] = None) -> None:
        try:
            self._run(agent_name=agent_name, mode="start")
        except (FileNotFoundError, RuntimeError) as e:
            # Only retry on file/model-related errors
            logger.info(f"Initial run failed with {type(e).__name__}: {e}. Attempting to download files...")
            self.download_files(agent_name)
            self._run(agent_name=agent_name, mode="start")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Agent start failed: {e}")
            raise

    def download_files(self, agent_name: Optional[str] = None, force: bool = True) -> None:
        """Download required model files.
        
        Args:
            agent_name: Name of the agent to download files for
            force: If True, force re-download even if files exist (fixes corrupted downloads)
        """
        self._run(agent_name=agent_name, mode="download-files", force_download=force)
            

    


