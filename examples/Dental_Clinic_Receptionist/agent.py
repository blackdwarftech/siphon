from siphon.agent import Agent, tool
from siphon.plugins import cartesia, openrouter, sarvam
from prompt import system_instructions
from dotenv import load_dotenv

load_dotenv()

llm = openrouter.LLM()
tts = cartesia.TTS()
stt = sarvam.STT()

agent = Agent(
    agent_name="Dental-Clinic-Receptionist",
    llm=llm,
    tts=tts,
    stt=stt,
    system_instructions=system_instructions,
    google_calendar=True
)

if __name__ == "__main__":

    # One-time setup: downloads required files (only needed on fresh machines)
    # agent.download_files()
    
    # For local development (logs, quick iteration)
    agent.dev()
    
    # For production workers, use:
    # agent.start()