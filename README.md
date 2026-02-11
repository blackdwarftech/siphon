<p align="center">
  <img src="https://siphon.blackdwarf.in/logo.png" alt="SIPHON" width="100" />
</p>

<h1 align="center">SIPHON</h1>

<p align="center">
  <a href="https://siphon.blackdwarf.in/docs">
    <img src="https://img.shields.io/badge/Documentation-000000?style=for-the-badge&logo=readthedocs&logoColor=white" alt="Documentation">
  </a>
  <a href="https://opensource.org/license/apache-2-0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-D22128?style=for-the-badge&logo=Apache&logoColor=white" alt="License">
  </a>
  <a href="https://pypi.org/project/siphon-ai/">
    <img src="https://img.shields.io/pypi/v/siphon-ai?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI">
  </a>
</p>

<h3 align="center">
  <strong>Open-source, low-latency Voice AI.</strong><br/>
  No markups. No lock-in. No middlemen.
</h3>

<p align="center">
  <strong>Built for teams who want full control</strong> over their calling AI stack,<br/>
  from infrastructure to data to cost.
</p>

⭐ Drop a star to help us grow!

<br/>

<p align="center">
  <img src="https://siphon.blackdwarf.in/system_overview.png" alt="SIPHON Architecture" width="100%" />
</p>

<br/>

## What Siphon is

Siphon is a **Python framework** that handles the hard parts of real-time voice AI:

- ✅ **SIP + telephony integration** — Connect to any SIP trunk (Twilio, Telnyx, SignalWire, etc.)
- ✅ **Streaming audio pipelines** — Sub-500ms latency powered by WebRTC (LiveKit)
- ✅ **Interruptions & barge-in** — Natural conversation flow with configurable turn detection
- ✅ **Agent state management** — Recording, transcription, metadata persistence
- ✅ **Horizontal scaling** — Run 1 or 1,000 workers with zero-config load balancing

**So you can focus on agent behavior, not call plumbing.**

### You bring:
- 🤖 Your LLM (OpenAI, Anthropic, Google, DeepSeek, Groq, Cerebras, Mistral, etc.)
- 🎤 Your STT/TTS providers (Deepgram, Cartesia, ElevenLabs, AssemblyAI, Sarvam, etc.)
- 📞 Your SIP trunk (Twilio, Telnyx, SignalWire, or self-hosted)
- ☁️ Your infrastructure (LiveKit Cloud or self-hosted)

### You keep:
- 💰 **Your margins** — No per-minute markup on AI provider costs
- 🔒 **Your data** — Runs on your infrastructure, all logs stay with you
- 📊 **Your observability** — Complete control over recording, transcription, metadata
- 🔑 **Your keys** — Direct integration with AI providers, no middleman

<br/>

## What Siphon is not

❌ **Not a SaaS platform** — You host it, you control it  
❌ **Not a black box** — Open-source (Apache 2.0), inspect and modify everything  
❌ **Not a per-minute tax** — No markup on your AI provider costs  
❌ **Not vendor lock-in** — Swap LLM/STT/TTS providers with a config change

<br/>

## Why Siphon exists

**Voice agents listen to everything.**

Your customers' calls contain sensitive information — personal details, business data, private conversations.

Traditional managed platforms route every call through their infrastructure. You pay per minute and trust them with your data.

**Siphon runs on your infrastructure.**  
You own the keys. You control the data. You keep the margins.

<br/>

---

## Production-Ready Architecture

| ⚡ **Low Latency** | 🛡️ **Production Ready** | 🚀 **Infinite Scale** |
| :--- | :--- | :--- |
| Powered by WebRTC (LiveKit) for sub-500ms voice interactions that feel like real human conversation. | Handles the chaotic reality of phone networks—audio packet loss, SIP signaling, and interruptions. | Define your agent once and run it on 1 or 1,000 servers. It balances the load automatically. |

<br/>


## Quick Start
 
If you're new to Siphon, we recommend checking out:
- 📖 **[Documentation](https://siphon.blackdwarf.in/docs)**
- ⚡ **[Quick Start Guide](https://siphon.blackdwarf.in/docs/overview/getting-started)**

### 1. Install
```bash
pip install siphon-ai
```

### 2. Configure Environment
Siphon requires **LiveKit** for real-time media and API keys for your AI providers.

Create a `.env` file:
```bash
# LiveKit (Cloud: https://cloud.livekit.io/ or Self-hosted)
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

# AI Providers
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
```

### 3. Create your Agent
Create a file named `agent.py`. This simple agent acts as a helpful assistant.

```python
from siphon.agent import Agent
from siphon.plugins import openai, cartesia, deepgram
from dotenv import load_dotenv

load_dotenv()

# Initialize your AI stack
llm = openai.LLM()
tts = cartesia.TTS()
stt = deepgram.STT()

# Define the Agent
agent = Agent(
    agent_name="Receptionist",
    llm=llm,
    tts=tts,
    stt=stt,
    system_instructions="You are a helpful receptionist. Answer succinctly.",
)

if __name__ == "__main__":
    # One-time setup: downloads required files (only needed on fresh machines)
    agent.download_files()

    # Start the agent worker in development mode
    agent.dev()

    # Start the agent worker in production mode
    # agent.start()
```

For more details on configuring your **[Agent](https://siphon.blackdwarf.in/docs/agents/overview)** (latency, interruptions, VAD...etc) and exploring available **[Plugins](https://siphon.blackdwarf.in/docs/plugins/overview)** (Deepgram, Cartesia, OpenAI, ElevenLabs...etc), check out the documentation.


### 4. Run
Start your agent worker.

```bash
python agent.py
```

**Horizontal Scaling**: To scale, simply run this command on multiple servers. The worker architecture automatically detects new nodes and balances the load with **Zero Configuration**. [Learn more about Scaling](https://siphon.blackdwarf.in/docs/concepts/scaling)


## Capabilities

### 📞 Receive Calls (Inbound)
Bind a phone number to your agent using a Dispatch rule.

```python
import os
from siphon.telephony.inbound import Dispatch
from dotenv import load_dotenv

load_dotenv()

dispatch = Dispatch(
    dispatch_name="customer-support",
    agent_name="Receptionist", # Must match the name in agent.py
    sip_trunk_id=os.getenv("SIP_TRUNK_ID"),
    # Or: sip_number=os.getenv("SIP_NUMBER"),
)
dispatch.agent()
```

> **Note**: For more details, check out the **[Inbound Documentation](https://siphon.blackdwarf.in/docs/calling/inbound/overview)**. To configure numbers with providers like Twilio, see the **[Twilio Setup Guide](https://siphon.blackdwarf.in/docs/guides/twilio)**.

### 📱 Make Calls (Outbound)
Trigger calls programmatically from your code or API.

```python
import os
from siphon.telephony.outbound import Call
from dotenv import load_dotenv

load_dotenv()

call = Call(
    agent_name="Receptionist", # Must match the name in agent.py
    sip_trunk_setup={ ... }, # Your SIP credentials
    # Or: sip_trunk_id=os.getenv("SIP_TRUNK_ID"),
    number_to_call="+15550199"
)
call.start()
```

> **Note**: For more details, check out the **[Outbound Documentation](https://siphon.blackdwarf.in/docs/calling/outbound/overview)**. To configure trunks with providers like Twilio, see the **[Twilio Setup Guide](https://siphon.blackdwarf.in/docs/guides/twilio)**.

### 💾 Persist Call Data
Siphon enables call recordings, transcriptions, and metadata persistence via environment variables.

```bash
# Enable saving features
CALL_RECORDING=true
SAVE_METADATA=true
SAVE_TRANSCRIPTION=true

# Configure storage location (locally, S3, Redis, Postgres, etc)
METADATA_LOCATION=Metadata # saves locally
TRANSCRIPTION_LOCATION=postgresql://..... # saves to postgresql

# Configure S3 (Call Recordings are always saved to S3)
AWS_S3_ENDPOINT=
AWS_S3_ACCESS_KEY_ID=
AWS_S3_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_S3_REGION=
AWS_S3_FORCE_PATH_STYLE=true
```

> **Note**: Siphon supports multiple storage backends. For detailed configuration instructions, see the **[Call Data Documentation](https://siphon.blackdwarf.in/docs/agents/call-data)**.

## 🚀 Examples and demo

> [**More Examples**](https://siphon.blackdwarf.in/examples)

| Example | Description |
| :--- | :--- |
| [**A 24/7 AI Dental Receptionist in few lines**](https://github.com/blackdwarftech/siphon/tree/main/examples/Dental_Clinic_Receptionist) | A fully functional AI receptionist that handles appointment booking, modifications, and cancellations with Google Calendar integration. |

More coming and stay tuned 👀!

## 📖 Documentation

For detailed documentation, visit [Siphon Documentation](https://siphon.blackdwarf.in/docs), including a [Quickstart Guide](https://siphon.blackdwarf.in/docs/overview/getting-started).

## 🤝 Contributing

We love contributions from the community ❤️. For details on contributing or running the project for development, check out our [Contributing Guide](https://github.com/blackdwarftech/siphon/blob/main/CONTRIBUTING.md).

## Support us

We are constantly improving, and more features and examples are coming soon. If you love this project, please drop us a star ⭐ at [GitHub repo](https://github.com/blackdwarftech/siphon) to stay tuned and help us grow.

## License

Siphon is Apache 2.0 licensed.
