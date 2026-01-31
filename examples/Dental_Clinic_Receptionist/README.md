# A 24/7 Dental Clinic Receptionist

A production-ready AI receptionist for dental clinics built with [SIPHON](https://github.com/blackdwarftech/siphon). This intelligent voice agent handles appointment booking, modifications and cancellations.

## Architecture

```
Dental_Clinic_Receptionist/
├── agent.py           # Main agent setup with system instructions
├── prompt.py          # Comprehensive system prompt with workflows
├── inbound.py         # Inbound call dispatch configuration
├── outbound.py        # Outbound call configuration
└── .env               # Environment variables (create from .env.example)
```

## Prerequisites

- Python 3.10 or higher
- SIPHON installed (`pip install siphon-ai`)
- AI Provider API keys (OpenRouter for LLM, Sarvam/Cartesia for TTS/STT)
- SIP trunk credentials (Twilio, Telnyx, etc.)
- Google Calendar API credentials

## Installation

### 1. Clone the SIPHON Repository

```bash
git clone https://github.com/blackdwarftech/siphon.git
cd siphon
```

### 2. Install SIPHON

```bash
pip install siphon-ai
```

### 3. Navigate to Example Directory

```bash
cd examples/Dental_Clinic_Receptionist
```

### 4. Set Up Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# LLM Provider (OpenRouter)
OPENROUTER_API_KEY=your_openrouter_api_key

# TTS Provider (Sarvam AI)
SARVAM_API_KEY=your_sarvam_api_key

# STT Provider (Sarvam AI)
# Uses same SARVAM_API_KEY

# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Google Calendar
GOOGLE_CALENDAR_ID=your_calendar_id@group.calendar.google.com
GOOGLE_CALENDAR_CREDENTIALS_PATH=/path/to/credentials.json

# Call Data Features
# These flags enable automatic capturing of call artifacts
CALL_RECORDING=false           # Set to true to enable recordings (requires S3 config below)
SAVE_METADATA=true             # Saves call details (duration, status, cost)
SAVE_TRANSCRIPTION=true        # Saves full conversation history

# Storage Configuration
# Metadata and transcriptions are saved locally by default. 
# To save to S3, set METADATA_LOCATION=s3 and TRANSCRIPTION_LOCATION=s3
METADATA_LOCATION=Call_Metadata
TRANSCRIPTION_LOCATION=Transcriptions

# S3 Configuration (Required for Recordings, optional for Metadata/Transcriptions)
# AWS_S3_ENDPOINT=http://localhost:9000
# AWS_S3_ACCESS_KEY_ID=minioadmin
# AWS_S3_SECRET_ACCESS_KEY=minioadmin
# AWS_S3_BUCKET=siphon
# AWS_S3_REGION=us-east-1
# AWS_S3_FORCE_PATH_STYLE=true
```

> **📅 Need help with Google Calendar setup?** See [Google Calendar Setup](./CALENDAR_SETUP.md) for step-by-step instructions on creating service account credentials.

## Running the Agent

### Development Mode (Local Testing)

Start the agent worker in development mode:

```bash
python agent.py
```

This will:
- Start the agent worker
- Wait for incoming calls or dispatch outbound calls

### Inbound Calls

To handle inbound calls, run the dispatch script:

```bash
python inbound.py
```

**Configure in `inbound.py`:**
- `agent_name`: Must match the name in `agent.py` (default: `Dental-Clinic-Receptionist`)
- `sip_number`: Your SIP trunk phone number

### Outbound Calls

To make outbound calls:

```bash
python outbound.py
```

**Configure in `outbound.py`:**
- `agent_name`: Must match the name in `agent.py`
- `sip_trunk_setup`: Your SIP provider credentials
- `number_to_call`: Target phone number

## Production Scaling:
For high-volume production deployments, you can run multiple instances of your agent script horizontally. It automatically distributes calls across available workers.
[Learn more about Horizontal Scaling](/docs/concepts/scaling)

## 📖 Documentation 

This example provides a starting point. For detailed customization options, refer to the official SIPHON documentation:

- **[LLM Plugins](https://siphon.blackdwarf.in/docs/plugins/llm/overview)** - How to add or change language models (OpenAI, Anthropic, Groq, etc.)
- **[TTS Plugins](https://siphon.blackdwarf.in/docs/plugins/tts/overview)** - Text-to-speech providers and voice configuration
- **[STT Plugins](https://siphon.blackdwarf.in/docs/plugins/stt/overview)** - Speech-to-text providers and transcription settings
- **[Inbound Calling](https://siphon.blackdwarf.in/docs/calling/inbound/overview)** - Complete guide to inbound call configuration
- **[Outbound Calling](https://siphon.blackdwarf.in/docs/calling/outbound/overview)** - Complete guide to outbound call configuration
- **[Agent Configuration](https://siphon.blackdwarf.in/docs/agents/configuration)** - Advanced agent settings and customization options
- **[Call Data & Observability](/docs/agents/call-data)** - Recordings, transcripts, and metadata

## How It Works

### Conversation Workflows

The agent follows structured workflows defined in `prompt.py`:

#### **1. New Appointment Booking**
```
1. Greet caller
2. Collect: Name, Phone, Reason for visit
3. Read back information for confirmation
4. Ask for preferred date/time
5. Check calendar availability
6. Create appointment with details in description
7. Confirm booking
```

#### **2. Modify Existing Appointment**
```
1. Acknowledge modification request
2. Verify identity (name + phone)
3. Search for appointments by phone number
4. Display only their appointments
5. Get new preferred date/time
6. Update appointment
7. Confirm changes
```

#### **3. Cancel Appointment**
```
1. Acknowledge cancellation request
2. Verify identity (name + phone)
3. Search and display their appointments
4. Confirm which appointment to cancel
5. Delete appointment
6. Confirm cancellation
```

## Troubleshooting

### Agent Not Responding

1. **Check if worker is running**: `python agent.py` should show "Agent entering room..."
2. **Verify credentials**: Ensure API keys in `.env` are correct
3. **Restart agent**: Stop and restart after code changes

### Calendar Not Working

1. Verify `GOOGLE_CALENDAR_CREDENTIALS_PATH` is correct
2. Ensure calendar ID is set in `.env`
3. Check that `google_calendar=True` in `agent.py`

> **📅 Need help with Google Calendar setup?** See [Google Calendar Setup](./CALENDAR_SETUP.md) for step-by-step instructions on creating service account credentials.

## Learn More

- **Main Repository**: [https://github.com/blackdwarftech/siphon](https://github.com/blackdwarftech/siphon)
- **Documentation**: [https://siphon.blackdwarf.in/docs](https://siphon.blackdwarf.in/docs)
- **More Examples**: [https://siphon.blackdwarf.in/examples](https://siphon.blackdwarf.in/examples)

## Support

For issues or questions:
- **GitHub Issues**: [Open an issue](https://github.com/blackdwarftech/siphon/issues)
- **Discord**: [Connect with us](https://discord.gg/ceD29rUTP)
- **Twitter/X**: [@blackdwarf__](https://x.com/blackdwarf__)
- **Email**: [siphon@blackdwarf.in](mailto:siphon@blackdwarf.in)
- **Documentation**: [https://siphon.blackdwarf.in/docs](https://siphon.blackdwarf.in/docs)

---

**⭐ If you found this helpful, please [star us on GitHub](https://github.com/blackdwarftech/siphon)!**
