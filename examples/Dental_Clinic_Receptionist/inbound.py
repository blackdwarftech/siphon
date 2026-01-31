import asyncio
from siphon.telephony.inbound import Dispatch
from dotenv import load_dotenv

load_dotenv()

dispatch = Dispatch(
    agent_name="Dental-Clinic-Receptionist",  # must match the agent_name used when defining/starting your agent worker
    dispatch_name="inbound-Dental-Clinic-Receptionist",
    sip_number="" #"+17432235294"   # from your SIP Provider
)

result = dispatch.agent()
print(result)

