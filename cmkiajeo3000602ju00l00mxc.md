---
title: "We Open-Sourced Our AI Calling Framework (So You Don't Waste 2-3 Months)"
seoTitle: "Open-Source AI Calling Framework Released"
seoDescription: "Siphon streamlines telephony for easy development of intelligent voice agents, focusing on conversations and bypassing infrastructure complexities"
datePublished: Sat Jan 17 2026 12:35:49 GMT+0000 (Coordinated Universal Time)
cuid: cmkiajeo3000602ju00l00mxc
slug: we-open-sourced-our-ai-calling-framework-so-you-dont-waste-2-3-months
cover: https://cdn.hashnode.com/res/hashnode/image/upload/v1768653178425/9c4396c4-91f3-46ea-bc5c-c23a3e1f9045.png
tags: ai, framework, python, opensource-inactive, developer-tools, ai-tools, agentic-ai

---

**Three months.**  
That’s how long many teams spend building telephony infrastructure before writing a single line of actual conversation logic for an AI voice agent.

Not because the AI was hard.  
Because **telephony is brutal**.

Today, we’re open-sourcing the solution so you don’t have to go through the same pain.

---

## **The Hidden Problem with AI Calling Agents**

Building an AI calling agent sounds straightforward:

* Use an LLM
    
* Add speech-to-text
    
* Add text-to-speech
    
* Connect it to a phone number
    

In reality, that’s where most teams hit a wall.

To make *real phone calls*, you end up dealing with:

* **SIP trunks & PSTN providers**
    
* **Low-latency, bidirectional audio**
    
* **Real-time orchestration of STT, LLM, and TTS**
    
* **Call state, interruptions, transfers**
    
* **Scaling, monitoring, recordings, persistence**
    

The result?  
Most teams spend **weeks or months on infrastructure** before they ever touch the conversation itself.

We did too. And eventually asked:

> *“Why is building voice AI still this hard?”*

---

## **Introducing Siphon**

**Siphon** is an open-source Python framework that handles the telephony complexity for you, so you can focus on building great conversations.

Here’s what a complete AI receptionist looks like with Siphon:

```python
from siphon.agent import Agent
from siphon.plugins import openai, cartesia, deepgram

agent = Agent(
    agent_name="receptionist",
    llm=openai.LLM(model="gpt-4"),
    tts=cartesia.TTS(voice="helpful-assistant"),
    stt=deepgram.STT(model="nova-2"),
    system_instructions="""
    You are a friendly receptionist for Acme Corp.
    Help callers schedule appointments or route them correctly.
    """
)

if __name__ == "__main__":
    agent.start()
```

Run this, and your agent can answer **real phone calls** via any SIP provider (Twilio, Telnyx, etc.).

---

## **What Siphon Handles for You**

* 🔌 **SIP & PSTN connectivity**  
    Works with any SIP provider, no FreeSWITCH pain.
    
* ⚡ **Real-time audio pipeline**  
    Built on LiveKit with streaming audio and **sub-500ms voice-to-voice latency**.
    
* 🤖 **AI orchestration**  
    Plug-and-play support for LLMs, STT, and TTS.
    

Swap providers with a single line:

```python
  llm=anthropic.LLM(model="claude-3-5-sonnet")
```

* 📈 **Production-ready by default** Auto-scaling, call recordings, transcripts, state handling, and observability.
    

---

## **Quick Start**

Install:

```bash
pip install siphon-ai
```

Create an agent:

```python
from siphon.agent import Agent
from siphon.plugins import openai, cartesia, deepgram

agent = Agent(
    agent_name="my_first_agent",
    llm=openai.LLM(),
    tts=cartesia.TTS(),
    stt=deepgram.STT(),
    system_instructions="You are a helpful assistant.",
)

agent.start()
```

That’s it.  
Your agent is live and answering phone calls.

(Full setup, outbound calling, and advanced examples are in the docs.)

---

## **Why We Open-Sourced It**

We could’ve kept Siphon proprietary or turned it into a closed SaaS.

But we believe **voice AI shouldn’t be locked behind massive infrastructure effort**.

Siphon is:

* **Apache 2.0 licensed**
    
* **Provider-agnostic**
    
* **Fully self-hostable**
    
* **No vendor lock-in**
    

Use it commercially, modify it, or build on top of it.

---

## **What You Can Build**

* 📞 Customer support agents
    
* 📅 Appointment scheduling
    
* 💼 Sales qualification
    
* 📊 Surveys & feedback collection
    
* 🏥 Healthcare intake systems
    

If it involves phone calls and conversations, Siphon handles the hard parts.

---

## **Get Involved**

⭐ GitHub: [https://github.com/blackdwarftech/siphon](https://github.com/blackdwarftech/siphon)  
📖 Docs: [https://siphon.blackdwarf.in/docs](https://siphon.blackdwarf.in/docs)  
🐛 Issues & feature requests welcome  
🤝 PRs encouraged

We’re building Siphon in public and would love community feedback.

---

If you’ve ever thought

> *“I wish building AI calling agents was simpler”*

— give Siphon a try.

**Built by BLACKDWARF**  
*Mission: Democratize complex technologies for developers.*