import asyncio
from siphon.telephony.outbound import Call
from siphon.plugins import sarvam
from dotenv import load_dotenv

load_dotenv()

stt = sarvam.STT()

call = Call(
    agent_name="Dental-Clinic-Receptionist",  # must match the agent_name used when defining/starting your agent worker
    sip_trunk_setup={
        "name": "Dental-Clinic-Receptionist",
        "sip_address": "",
        "sip_number": "",
        "sip_username": "",
        "sip_password": ""
    },
    number_to_call=""
)

result = call.start()
print(result)