from typing import Dict, Any, Optional
from livekit import api
from livekit.protocol.sip import ListSIPInboundTrunkRequest
import uuid

class Trunk:
    """Small helper for managing LiveKit SIP Inbound trunks."""
    def __init__(self) -> None:
        ...

    async def create_trunk(
        self,
        name: Optional[str] = uuid.uuid4().hex,
        sip_number: str = None,
    ) -> Dict[str, Any]:
        lkapi = api.LiveKitAPI()

        trunk = api.SIPInboundTrunkInfo(
            name = name,
            numbers = [sip_number],
            krisp_enabled = True,
        )

        try:
            request = api.CreateSIPInboundTrunkRequest(
                trunk = trunk
            )
            trunk = await lkapi.sip.create_inbound_trunk(request)
            return {
                "trunk_id": trunk.sip_trunk_id
            }
        except Exception as e:
            return {
                "trunk_id": None,
                "Error": e
            }
        finally:
            await lkapi.aclose()


    async def get_trunk(self, sip_number: str) -> Dict[str, Any]:
        """Look up an existing inbound trunk by phone number.

        Returns a dict with keys:
          - trunk_id: the trunk id if found, else None
        """

        lkapi = api.LiveKitAPI()

        try:
            # List all inbound trunks and filter locally by configured numbers.
            request = ListSIPInboundTrunkRequest()
            trunks = await lkapi.sip.list_sip_inbound_trunk(request)

            for trunk in trunks.items or []:
                numbers = getattr(trunk, "numbers", []) or []
                if sip_number in numbers:
                    return {
                        "trunk_id": trunk.sip_trunk_id,
                    }

            return {
                "trunk_id": None,
            }
        except Exception as e:
            return {
                "trunk_id": None,
                "Error": e,
            }
        finally:
            await lkapi.aclose()


    async def get_trunk_by_id(self, trunk_id: str) -> Dict[str, Any]:
        """Look up an existing inbound trunk by its ID and return basic info.

        Returns a dict with keys:
          - trunk_id: the trunk id if found, else None
          - sip_number: the first configured number on the trunk (if any)
        """

        lkapi = api.LiveKitAPI()

        try:
            # List all inbound trunks and filter locally by ID.
            request = ListSIPInboundTrunkRequest()
            trunks = await lkapi.sip.list_sip_inbound_trunk(request)

            for trunk in trunks.items or []:
                if trunk.sip_trunk_id == trunk_id:
                    numbers = getattr(trunk, "numbers", []) or []
                    primary_number = numbers[0] if numbers else None
                    return {
                        "trunk_id": trunk.sip_trunk_id,
                        "sip_number": primary_number,
                    }

            return {
                "trunk_id": None,
                "sip_number": None,
            }
        except Exception as e:
            return {
                "trunk_id": None,
                "sip_number": None,
                "Error": e,
            }
        finally:
            await lkapi.aclose()


    async def delete_trunk(
        self, 
        trunk_id: Optional[str] = None,
        sip_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete an inbound SIP trunk by trunk_id or sip_number.

        Args:
            trunk_id: The SIP trunk ID to delete (optional)
            sip_number: The phone number to find and delete the trunk (optional)

        Returns a dict with keys:
          - success: True if deleted, False otherwise
          - trunk_id: the deleted trunk id if successful
          - Error: error message if failed
        """
        if not trunk_id and not sip_number:
            return {
                "success": False,
                "trunk_id": None,
                "Error": "Either trunk_id or sip_number must be provided"
            }

        lkapi = api.LiveKitAPI()

        try:
            # If sip_number provided, first find the trunk_id
            if not trunk_id and sip_number:
                trunk_info = await self.get_trunk(sip_number)
                trunk_id = trunk_info.get("trunk_id")
                
                if not trunk_id:
                    return {
                        "success": False,
                        "trunk_id": None,
                        "Error": f"No trunk found for number {sip_number}"
                    }

            # Delete the trunk using the trunk_id
            request = api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id)
            await lkapi.sip.delete_sip_trunk(request)
            
            return {
                "success": True,
                "trunk_id": trunk_id,
            }
        except Exception as e:
            return {
                "success": False,
                "trunk_id": trunk_id,
                "Error": e,
            }
        finally:
            await lkapi.aclose()
