from typing import Dict, Any, Optional

from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo, ListSIPOutboundTrunkRequest


class Trunk:
    """Small helper for managing LiveKit SIP outbound trunks."""

    def __init__(self) -> None:
        ...

    async def create_trunk(
        self,
        name: Optional[str] = "Telephony-Agent",
        sip_address: str = None,
        sip_number: str = None,
        sip_username: str = None,
        sip_password: str = None
    ) -> Dict[str, Any]:
        """Create a new outbound trunk and return its id (if successful)."""
        trunk = SIPOutboundTrunkInfo(
            name = name,
            address = sip_address,
            numbers = [sip_number],
            auth_username = sip_username,
            auth_password = sip_password
        )

        request = CreateSIPOutboundTrunkRequest(
            trunk = trunk
        )

        lkapi = api.LiveKitAPI()

        try:
            trunk = await lkapi.sip.create_outbound_trunk(request)
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


    async def get_trunk(
        self,
        sip_address: str,
        sip_number: str,
        sip_username: str
    ) -> Dict[str, Any]:
        """Look up an existing outbound trunk matching the given settings."""

        lkapi = api.LiveKitAPI()

        try:
            request = ListSIPOutboundTrunkRequest(numbers=[sip_number])
            trunks = await lkapi.sip.list_outbound_trunk(request)
            
            for trunk in trunks.items or []:
                if trunk.address == sip_address and sip_number in trunk.numbers and trunk.auth_username == sip_username:
                    return {
                        "trunk_id": trunk.sip_trunk_id
                    }
            
            return {
                "trunk_id": None
            }
        except Exception as e:
            return {
                "trunk_id": None,
                "Error": e
            }
        finally:
            await lkapi.aclose()


    async def get_trunk_by_id(self, trunk_id: str) -> Dict[str, Any]:
        """Look up an existing outbound trunk by its ID and return basic info.

        Returns a dict with keys:
          - trunk_id: the trunk id if found, else None
          - sip_number: the first configured number on the trunk (if any)
        """

        lkapi = api.LiveKitAPI()

        try:
            # List all trunks and filter by ID. This avoids depending on
            # any particular filter fields on ListSIPOutboundTrunkRequest.
            request = ListSIPOutboundTrunkRequest()
            trunks = await lkapi.sip.list_outbound_trunk(request)

            for trunk in trunks.items or []:
                if trunk.sip_trunk_id == trunk_id:
                    primary_number = trunk.numbers[0] if getattr(trunk, "numbers", None) else None
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
        """Delete an outbound SIP trunk by trunk_id or sip_number.

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
                # List all trunks and find by number
                request = ListSIPOutboundTrunkRequest(numbers=[sip_number])
                trunks = await lkapi.sip.list_outbound_trunk(request)
                
                for trunk in trunks.items or []:
                    if sip_number in trunk.numbers:
                        trunk_id = trunk.sip_trunk_id
                        break
                
                if not trunk_id:
                    await lkapi.aclose()
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


