import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
from livekit import api
import uuid
import asyncio

from .trunk import Trunk
from siphon.config import get_logger

logger = get_logger("make-call")

class SIPConfig(BaseModel):
    name: Optional[str] = uuid.uuid4().hex,
    sip_address: str = None,
    sip_number: str = None,
    sip_username: str = None,
    sip_password: str = None

class Call:
    def __init__(
        self,
        id: Optional[str] = None,
        agent_name: Optional[str] = "Calling-Agent-System",
        sip_trunk_id: Optional[str] = None,
        number_to_call_from: Optional[str] = None,
        sip_trunk_setup: Optional[SIPConfig] = None,
        number_to_call: str = None,
        llm: Optional[Any] = None,
        stt: Optional[Any] = None,
        tts: Optional[Any] = None,
        greeting_instructions: Optional[str] = None,
        system_instructions: Optional[str] = None,
        wait_until_answered: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Configure and initiate a single outbound telephony call.

        The Call instance holds both telephony config (trunk, numbers) and the
        agent configuration that will be passed to the LiveKit Agent worker via
        dispatch metadata.
        """

        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
        
        self.agent_name = agent_name

        self.sip_trunk_id = sip_trunk_id
        self.number_to_call_from = number_to_call_from
        self.number_to_call = number_to_call

        self.llm = llm
        self.tts = tts
        self.stt = stt
        self.greeting_instructions = greeting_instructions
        self.system_instructions = system_instructions

        self.wait_until_answered = wait_until_answered

        if self.number_to_call is None:
            raise ValueError("number_to_call is required")

        #----- SIP Config -----
        if isinstance(sip_trunk_setup, dict):
            sip_trunk_setup = SIPConfig(**sip_trunk_setup)

        if sip_trunk_setup:
            self.sip_name = sip_trunk_setup.name
            self.sip_address = sip_trunk_setup.sip_address
            self.sip_number = sip_trunk_setup.sip_number
            self.sip_username = sip_trunk_setup.sip_username
            self.sip_password = sip_trunk_setup.sip_password
        else:
            self.sip_name = None
            self.sip_address = None
            self.sip_number = None
            self.sip_username = None
            self.sip_password = None

        #----- Agent Config -----
        llm_cfg = self.llm.to_config() if hasattr(self.llm, "to_config") else None
        tts_cfg = self.tts.to_config() if hasattr(self.tts, "to_config") else None
        stt_cfg = self.stt.to_config() if hasattr(self.stt, "to_config") else None
        
        # Metadata is forwarded to the Agent worker via CreateAgentDispatch.
        self.metadata = {
            "number_to_call": self.number_to_call,
            "standalone_call": True,
            "agent_config": {
                "llm": llm_cfg,
                "tts": tts_cfg,
                "stt": stt_cfg,
                "greeting_instructions": self.greeting_instructions,
                "system_instructions": self.system_instructions
            },
        }

    #----- SIP Trunk Setup -----
    async def _setup_trunk(self):
        """Ensure there is an outbound SIP trunk id available for the call.

        Either uses an explicit sip_trunk_id or looks up/creates one from the
        provided SIPConfig. Raises ValueError if nothing can be resolved.
        """
        trunk = Trunk()
        self.outbound_trunk_id = None

        # When an explicit sip_trunk_id is provided (no SIP config object)
        if self.sip_trunk_id is not None:
            self.outbound_trunk_id = self.sip_trunk_id

            # If the caller did not provide a from-number, try to infer it
            # from the trunk configuration itself.
            if not self.number_to_call_from:
                try:
                    trunk_info = await trunk.get_trunk_by_id(self.sip_trunk_id)
                    inferred_number = trunk_info.get("sip_number")
                    if inferred_number:
                        self.number_to_call_from = inferred_number
                except Exception as e:
                    logger.error("Failed to infer from-number from trunk %s: %s", self.sip_trunk_id, e)

        # When sip trunk setup is given 
        if self.sip_address is not None and self.sip_trunk_id is None:
            # get trunk id if exists or create new one
            trunk_id = await trunk.get_trunk(
                sip_address=self.sip_address,
                sip_number=self.sip_number,
                sip_username=self.sip_username
            )
            if trunk_id and trunk_id.get("trunk_id") is not None:
                self.outbound_trunk_id = trunk_id["trunk_id"]
            else:
                new_trunk = await trunk.create_trunk(
                    name=self.sip_name,
                    sip_address=self.sip_address,
                    sip_number=self.sip_number,
                    sip_username=self.sip_username,
                    sip_password=self.sip_password
                )
                self.outbound_trunk_id = new_trunk.get("trunk_id")
            
            self.number_to_call_from = self.sip_number

        # Propagate resolved trunk and agent number into metadata for downstream consumers
        if self.outbound_trunk_id:
            self.metadata["outbound_trunk_id"] = self.outbound_trunk_id
        if self.number_to_call_from:
            self.metadata["agent_number"] = self.number_to_call_from

        if not self.outbound_trunk_id:
            raise ValueError("No SIP outbound trunk configured. Provide 'sip_trunk_id' or 'sip_trunk_setup'.")

    async def start_call(self):
        """Resolve trunk configuration and place the outbound call.

        Returns a dict containing dispatch and SIP identifiers, plus an error
        field when something goes wrong.
        """
        try:
            await self._setup_trunk()
        except Exception as e:
            logger.error("Failed to set up SIP trunk: %s", e)
            return {
                "dispatch_id": None,
                "sip_participant_id": None,
                "sip_call_id": None,
                "error": str(e),
            }

        call = await self.make_outbound_call(
            id=self.id,
            agent_name=self.agent_name,
            outbound_trunk_id=self.outbound_trunk_id,
            metadata=self.metadata,
            number_to_call_from=self.number_to_call_from,
            number_to_call=self.number_to_call,
            wait_until_answered=self.wait_until_answered,
        )

        return call

    async def make_outbound_call(
        self,
        id: str,
        agent_name: str,
        outbound_trunk_id: str,
        metadata: Dict[str, Any],
        number_to_call_from: str,
        number_to_call: str,
        wait_until_answered: bool
    ) -> Dict[str, Any]:
        lkapi = api.LiveKitAPI()

        result: Dict[str, Any] = {
            "agent_name": agent_name,
            "dispatch_id": None,
            "sip_participant_id": None,
            "sip_call_id": None,
            "error": None,
        }

        try:
            dispatch = await lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=agent_name,
                    room=id,
                    metadata=json.dumps(metadata),
                )
            )
            result["dispatch_id"] = dispatch.id
        except Exception as e:
            logger.error("Failed to create dispatch: %s", e)
            result["error"] = f"dispatch_error: {e}"
            await lkapi.aclose()
            return result

        try:
            sip_participant = await lkapi.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=id,
                    sip_trunk_id=outbound_trunk_id,
                    sip_number=number_to_call_from,
                    sip_call_to=number_to_call,
                    participant_identity=f"sip-{id}",
                    krisp_enabled=True,
                    wait_until_answered=wait_until_answered,
                )
            )
            result["sip_participant_id"] = sip_participant.participant_id
            result["sip_call_id"] = sip_participant.sip_call_id
        except api.TwirpError as e:
            logger.error("SIP Error: %s", e.message)
            if e.metadata:
                sip_status = e.metadata.get("sip_status_code")
                sip_message = e.metadata.get("sip_status")
                logger.error("SIP Status: %s - %s", sip_status, sip_message)
            result["error"] = f"sip_error: {e.message}"
        except Exception as e:
            logger.error("Error creating SIP participant: %s", e)
            result["error"] = f"sip_error: {e}"
        finally:
            await lkapi.aclose()

        return result

    def start(self):
        return asyncio.run(self.start_call())

