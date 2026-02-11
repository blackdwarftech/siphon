# The Sovereign Voice Manifesto

Voice AI is broken.

Not because the models are bad —  
but because **access is rationed by wrappers**.

---

## The Problem

Today's "Voice AI platforms" are toll booths.

They:

- Wrap public APIs (OpenAI, Deepgram, Cartesia)
- Add minimal orchestration
- Charge **per-minute rent**
- Lock you into black boxes
- Sit between you and your users' conversations

**At scale, this is insane.**

You pay:

- For your LLM
- For your STT
- For your TTS
- For your SIP trunk
- **And again** — just to connect them

This is not innovation.  
**It's rent-seeking.**

---

## The Cost Nobody Talks About

Voice agents hear **everything**:

- Medical data
- Financial details
- Sales conversations
- Private emotions
- Business secrets

### The Questions You Should Ask

- Where do your calls go?
- Who stores the recordings?
- Who can access the transcripts?
- What happens to the data after the call?

**"Trust us" is not a security model.**

When you route calls through a managed platform:
- You lose data sovereignty
- You accept their terms
- You hope they're secured
- You pay for the privilege

---

## What We Believe

### Ownership
- **You should own your calls** — not rent access to them
- **You should own your infrastructure** — not depend on someone else's
- **You should pay for compute** — not permission

### Technical Excellence
- **Latency matters** — and it's determined by your model choices, not our infrastructure
- **Interruptions matter** — Siphon gives you the controls, you tune them
- **Python developers** shouldn't be forced into Node or Go to ship voice

### Transparency
- Open source beats black boxes
- Direct integrations beat wrappers
- Standards beat vendor lock-in

---

## What Siphon Stands For

Siphon is **Sovereign Voice AI**.

| Principle | Implementation |
|-----------|----------------|
| 🔓 **Open Source** | Apache 2.0 license — inspect, modify, deploy |
| 🏠 **Your Infrastructure** | Runs on your cloud, your servers, your LiveKit |
| 💰 **No Platform Fees** | Pay your AI providers directly, no markup |
| 🔒 **No Hidden Routing** | Your calls go from SIP → LiveKit → your agent |
| 🔑 **No Lock-In** | Swap LLMs, STT, TTS providers with config changes |

---

## Build Agents That Speak For You

**Not for a platform.**

Siphon is not the easiest path.  
It is the **right** one.

If you want convenience, buy a wrapper.  
If you want control, **use Siphon**.

---

## Technical Recommendations

> **Note:** Latency and interruption handling depend heavily on your model choices. Siphon's infrastructure is optimized for sub-500ms latency — but the models you choose determine the final user experience.

### For Low-Latency Production (< 1 second end-to-end)

**Best Overall Stack:**
```python
LLM: Groq (Llama 3.3 70B) or Cerebras (Llama 3.1 8B)
STT: Deepgram Nova 3
TTS: Cartesia Sonic or ElevenLabs Turbo
```
- **Why:** Groq/Cerebras have 200-500ms time-to-first-token (TTFT)
- **Latency:** ~800ms-1.2s total (STT → LLM → TTS → audio)
- **Cost:** ~$0.02-$0.05/min (direct provider costs)

---

### For Best Quality (Natural Conversations)

**Premium Stack:**
```python
LLM: OpenAI GPT-4o or Anthropic Claude 3.5 Sonnet
STT: Deepgram Nova 3 or AssemblyAI
TTS: ElevenLabs (standard) or Cartesia Sonic
```
- **Why:** GPT-4o has excellent conversational ability and function calling
- **Latency:** ~1.5-2.5s total
- **Cost:** ~$0.05-$0.12/min (direct provider costs)

---

### For Cost-Sensitive Deployments

**Budget Stack:**
```python
LLM: DeepSeek V3 or Groq (Llama 3.1 8B)
STT: Deepgram Nova 2
TTS: Cartesia Sonic or OpenAI TTS
```
- **Why:** DeepSeek is incredibly cheap, Groq has free tier
- **Latency:** ~1-1.5s total
- **Cost:** ~$0.01-$0.03/min (direct provider costs)

---

### For Multilingual Support

**Global Stack:**
```python
LLM: OpenAI GPT-4o or Google Gemini 2.0 Flash
STT: Deepgram Nova 3 (multi-language) or Google STT
TTS: Sarvam AI (Hindi/Indic) or ElevenLabs (multilingual)
```
- **Why:** Gemini 2.0 Flash excels at multilingual, Sarvam optimized for Indic languages
- **Latency:** ~1.2-2s total
- **Cost:** ~$0.03-$0.08/min (direct provider costs)

---

### For Maximum Context & Complex Tasks

**Power Stack:**
```python
LLM: Anthropic Claude 3.5 Sonnet (200k context)
STT: Deepgram Nova 3
TTS: ElevenLabs or Cartesia
```
- **Why:** Claude 3.5 handles complex multi-step reasoning
- **Latency:** ~2-3s total (worth it for quality)
- **Cost:** ~$0.08-$0.15/min (direct provider costs)

---

### Interruption Handling

**For natural barge-in, configure:**

```python
Agent(
    allow_interruptions=True,
    min_interruption_duration=0.08,  # 80ms minimum to register
    min_endpointing_delay=0.45,      # 450ms before detecting turn end
    activation_threshold=0.4,         # VAD sensitivity (lower = more sensitive)
)
```

**Critical for interruptions:**
- ✅ **Fast LLM TTFT** — Groq, Cerebras, GPT-4o mini
- ✅ **Streaming TTS** — Cartesia, ElevenLabs Turbo
- ✅ **Low endpointing delay** — 400-600ms sweet spot

---

## Comparison: Managed Platform vs Siphon

| Aspect | Managed Platform (Vapi/Retell/Bland) | Siphon (Self-Hosted) |
|--------|--------------------------------------|----------------------|
| **Cost (10k minutes)** | $500-$3,100 + AI costs | $0 + AI costs ($200-$800) |
| **Data Routing** | Platform servers → your users | Your servers → your users |
| **Vendor Lock-In** | Hard (API-specific) | None (swap providers anytime) |
| **Observability** | Platform dashboard | Full control (your logs, your storage) |
| **Customization** | Limited to API parameters | Full code access |
| **Compliance** | Trust their security | You control security |
| **Latency** | Platform routing overhead | Direct LiveKit connection |
| **Scaling** | Platform limits | Your infrastructure limits |

---

## The Choice

You have two paths:

### Path 1: Managed Platform
- ✅ Quick to start
- ✅ Managed infrastructure
- ❌ Per-minute fees ($0.05-$0.30/min)
- ❌ Data goes through their servers
- ❌ Limited customization
- ❌ Vendor lock-in

### Path 2: Siphon (Sovereign)
- ✅ No platform fees
- ✅ Full data ownership
- ✅ Complete customization
- ✅ No vendor lock-in
- ❌ Requires setup (LiveKit + SIP)
- ❌ You manage infrastructure

**Choose wisely.**

---

## Join the Movement

Siphon is more than a framework.  
It's a statement.

**The future of voice AI is sovereign.**

- **Star us**: [github.com/blackdwarftech/siphon](https://github.com/blackdwarftech/siphon)
- **Contribute**: Help build the infrastructure for sovereign voice
- **Deploy**: Run voice agents on your terms

---

<p align="center">
  <strong>Built with Siphon.</strong><br/>
  <em>Owned by you.</em>
</p>
