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
        "sip_address": "siphon-testing7613.pstn.twilio.com",
        "sip_number": "+18703377189",
        "sip_username": "elt",
        "sip_password": "Password@123"
    },
    number_to_call="+917795341235" #"+919686110436" #"+917795341235"
)

result = call.start()
print(result)