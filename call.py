import asyncio
from siphon.telephony.outbound import Call
from siphon.plugins import sarvam
from dotenv import load_dotenv

load_dotenv()

stt = sarvam.STT()

call = Call(
    agent_name="Agent-System",  # must match the agent_name used when defining/starting your SIPHON agent worker
    sip_trunk_setup={
        "name": "Telephony-Agent-test",
        "sip_address": "siphon-trunk.pstn.twilio.com",
        "sip_number": "+16188222925",
        "sip_username": "siphon",
        "sip_password": "Password@123"
    },
    number_to_call="+917795341235"
)

result = call.start()
print(result)