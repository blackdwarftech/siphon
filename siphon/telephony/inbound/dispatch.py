from typing import Any, Optional, Dict
from livekit import api
from .trunk import Trunk
import json
import asyncio
from siphon.config import get_logger

logger = get_logger("dispatch")

class Dispatch:
    def __init__(
        self,
        agent_name: Optional[str] = "Calling-Agent-System",
        dispatch_name: Optional[str] = None,
        sip_trunk_id: Optional[str] = None,
        sip_number: Optional[str] = None,
        llm: Optional[Any] = None,
        stt: Optional[Any] = None,
        tts: Optional[Any] = None,
        greeting_instructions: Optional[str] = None,
        system_instructions: Optional[str] = None
    ) -> None:
        """Configure and dispatch an inbound agent setup.

        The Dispatch instance holds both telephony config (trunk, numbers) and the
        agent configuration that will be passed to the LiveKit Agent worker via
        dispatch metadata.
        """
        self.agent_name = agent_name
        self.dispatch_name = dispatch_name

        self.sip_trunk_id = sip_trunk_id
        self.sip_number = sip_number

        self.llm = llm
        self.tts = tts
        self.stt = stt
        self.greeting_instructions = greeting_instructions
        self.system_instructions = system_instructions

        #----- Agent Config -----
        llm_cfg = self.llm.to_config() if hasattr(self.llm, "to_config") else None
        tts_cfg = self.tts.to_config() if hasattr(self.tts, "to_config") else None
        stt_cfg = self.stt.to_config() if hasattr(self.stt, "to_config") else None
        
        # Metadata is forwarded to the Agent worker via CreateAgentDispatch.
        self.metadata = {
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
        """Ensure there is an Inbound SIP trunk id available for the dispatch agent.

        Either uses an explicit sip_trunk_id or looks up/creates one from the
        provided sip number. Raises ValueError if nothing can be resolved.
        """
        trunk = Trunk()
        self.inbound_trunk_id = None

        # When an explicit sip_trunk_id is provided (no SIP config object)
        if self.sip_trunk_id is not None:
            self.inbound_trunk_id = self.sip_trunk_id

            # If the caller did not provide a sip-number, try to infer it
            # from the trunk configuration itself.
            if not self.sip_number:
                try: 
                    trunk_info = await trunk.get_trunk_by_id(self.sip_trunk_id)
                    inferred_number = trunk_info.get("sip_number")
                    if inferred_number:
                        self.sip_number = inferred_number
                except Exception as e:
                    logger.error("Failed to infer from-number from trunk %s: %s", self.sip_trunk_id, e)
        

        # When sip trunk id is not given but we have a phone number,
        # either reuse an existing trunk for that number or create one.
        if self.sip_trunk_id is None and self.sip_number is not None:
            # get trunk id if exists or create new one
            trunk_id = await trunk.get_trunk(
                sip_number=self.sip_number
            )
            if trunk_id and trunk_id.get("trunk_id") is not None:
                self.inbound_trunk_id = trunk_id["trunk_id"]
            else:
                new_trunk = await trunk.create_trunk(
                    name=self.agent_name,
                    sip_number=self.sip_number,
                )
                self.inbound_trunk_id = new_trunk["trunk_id"]
            
        # Propagate resolved trunk and agent number into metadata for downstream consumers
        if self.inbound_trunk_id:
            self.metadata["inbound_trunk_id"] = self.inbound_trunk_id
        if self.sip_number:
            self.metadata["agent_number"] = self.sip_number

        if not self.inbound_trunk_id:
            raise ValueError("No SIP inbound trunk configured. Provide 'sip_trunk_id' or 'sip_trunk_setup'.")

    async def agent_dispatch(self):
        """Resolve trunk configuration and dispatch the inbound agent.

        Returns a dict containing dispatch and SIP identifiers, plus an error
        field when something goes wrong.
        """
        # Ensure we have a valid inbound trunk id and number in metadata
        try:
            await self._setup_trunk()
        except Exception as e:
            logger.error("Failed to set up SIP trunk: %s", e)
            return {"Error": e}

        lkapi = api.LiveKitAPI()

        # Create a dispatch rule for inbound calls
        rule = api.SIPDispatchRule(
            dispatch_rule_individual = api.SIPDispatchRuleIndividual(
                room_prefix = 'inbound-call-',
            )
        )

        try:
            request = api.CreateSIPDispatchRuleRequest(
                dispatch_rule = api.SIPDispatchRuleInfo(
                    rule = rule,
                    name = self.dispatch_name,
                    trunk_ids = [self.inbound_trunk_id],
                    room_config=api.RoomConfiguration(
                        agents=[api.RoomAgentDispatch(
                            agent_name=self.agent_name,
                            metadata=json.dumps(self.metadata),
                        )]
                    )
                )
            )
            dispatch = await lkapi.sip.create_sip_dispatch_rule(request)
            return dispatch
        except Exception as e:
            return {
                "Error": e
            }
        finally:
            await lkapi.aclose()

    def agent(self):
       return asyncio.run(self.agent_dispatch())


    async def get_dispatch_rule(
        self,
        dispatch_id: Optional[str] = None,
        sip_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find dispatch rule(s) by dispatch_id or sip_number.

        Args:
            dispatch_id: The dispatch rule ID to find (optional)
            sip_number: The phone number to find dispatch rules (optional)

        Returns a dict with keys:
          - dispatch_rules: list of dispatch rule dicts (each with id, name, trunk_ids)
          - count: number of dispatch rules found
          - Error: error message if failed
        """
        if not dispatch_id and not sip_number:
            return {
                "dispatch_rules": [],
                "count": 0,
                "Error": "Either dispatch_id or sip_number must be provided"
            }

        lkapi = api.LiveKitAPI()

        try:
            # List all dispatch rules
            request = api.ListSIPDispatchRuleRequest()
            dispatch_rules = await lkapi.sip.list_sip_dispatch_rule(request)

            matching_rules = []

            # If dispatch_id provided, find by ID
            if dispatch_id:
                for rule in dispatch_rules.items or []:
                    if rule.sip_dispatch_rule_id == dispatch_id:
                        matching_rules.append({
                            "dispatch_id": rule.sip_dispatch_rule_id,
                            "name": getattr(rule, "name", None),
                            "trunk_ids": getattr(rule, "trunk_ids", []),
                        })
            
            # If sip_number provided, find ALL rules using trunks with this number
            elif sip_number:
                # First find the trunk with this number
                trunk = Trunk()
                trunk_info = await trunk.get_trunk(sip_number)
                trunk_id = trunk_info.get("trunk_id")

                if trunk_id:
                    # Find ALL dispatch rules that use this trunk
                    for rule in dispatch_rules.items or []:
                        trunk_ids = getattr(rule, "trunk_ids", []) or []
                        if trunk_id in trunk_ids:
                            matching_rules.append({
                                "dispatch_id": rule.sip_dispatch_rule_id,
                                "name": getattr(rule, "name", None),
                                "trunk_ids": trunk_ids,
                            })

            if matching_rules:
                return {
                    "dispatch_rules": matching_rules,
                    "count": len(matching_rules),
                }
            else:
                return {
                    "dispatch_rules": [],
                    "count": 0,
                    "Error": "No dispatch rule found"
                }
        except Exception as e:
            return {
                "dispatch_rules": [],
                "count": 0,
                "Error": str(e),
            }
        finally:
            await lkapi.aclose()


    async def delete_dispatch_rule(
        self,
        dispatch_id: Optional[str] = None,
        sip_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete dispatch rule(s) by dispatch_id or sip_number.

        When using sip_number, ALL dispatch rules using that number will be deleted.

        Args:
            dispatch_id: The dispatch rule ID to delete (optional)
            sip_number: The phone number - deletes ALL dispatch rules using this number (optional)

        Returns a dict with keys:
          - success: True if at least one rule was deleted
          - deleted_count: number of dispatch rules deleted
          - deleted_ids: list of deleted dispatch rule IDs
          - Error: error message if failed
        """
        if not dispatch_id and not sip_number:
            return {
                "success": False,
                "deleted_count": 0,
                "deleted_ids": [],
                "Error": "Either dispatch_id or sip_number must be provided"
            }

        lkapi = api.LiveKitAPI()
        deleted_ids = []

        try:
            # If dispatch_id provided, delete that specific rule
            if dispatch_id:
                request = api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=dispatch_id)
                await lkapi.sip.delete_sip_dispatch_rule(request)
                deleted_ids.append(dispatch_id)
            
            # If sip_number provided, find and delete ALL matching rules
            elif sip_number:
                # First find all matching dispatch rules
                rule_info = await self.get_dispatch_rule(sip_number=sip_number)
                
                if rule_info.get("count", 0) == 0:
                    await lkapi.aclose()
                    return {
                        "success": False,
                        "deleted_count": 0,
                        "deleted_ids": [],
                        "Error": f"No dispatch rule found for number {sip_number}"
                    }
                
                rules_to_delete = rule_info.get("dispatch_rules", [])
                
                # Delete ALL matching rules
                for rule in rules_to_delete:
                    rule_id = rule["dispatch_id"]
                    request = api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=rule_id)
                    await lkapi.sip.delete_sip_dispatch_rule(request)
                    deleted_ids.append(rule_id)

            return {
                "success": True,
                "deleted_count": len(deleted_ids),
                "deleted_ids": deleted_ids,
            }
        except Exception as e:
            return {
                "success": False,
                "deleted_count": len(deleted_ids),
                "deleted_ids": deleted_ids,
                "Error": str(e),
            }
        finally:
            await lkapi.aclose()