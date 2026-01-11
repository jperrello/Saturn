Subject: ZeroconfAI Project Update - November 3, 2025

To whom it may concern,

I wanted to give you a detailed update on the ZeroconfAI project I've been working on with my mentor Adam.
## Project Overview: ZeroconfAI Protocol

The core idea is to create a discovery protocol for AI inference services on local networks using mDNS (Multicast DNS). The goal is to enable applications to integrate LLM capabilities without forcing end-users into complicated configurations or requiring developers to build entire subscription infrastructure around API keys.

**The Protocol Specification:**
- Service type: `_zeroconfai._tcp.local`
- Discovery returns IP:port pairs with priority metadata
- Each service exposes an OpenAI-compatible HTTP API with standard endpoints (I use FastAPI):
  - `/health` for service monitoring
  - `/v1/models` for capability discovery
  - `/v1/chat/completions` for inference requests

The beauty of this approach is language-agnostic implementation—any language with mDNS and HTTP libraries can participate in the ZeroconfAI ecosystem.

## Architectural Evolution

**Initial Vision (Pure Local):**
My original architecture centered on wrapping local Ollama instances. Each machine on a network could advertise its locally-running models via mDNS, and clients would discover and load-balance across them. This was appealing because it eliminated cloud dependencies entirely. A truly local, private AI inference.

**The Pivot (Hybrid Approach):**
Adam suggested pivoting to cloud-based providers (specifically OpenRouter) as the backend, which fundamentally changed the architecture. The Raspberry Pi gateway would become a lightweight proxy rather than handling inference directly.

This created some tension with the original vision. I raised several concerns:
1. **API key management** - Now we need per-household OpenRouter accounts
2. **Internet dependency** - The "local" service dies without WAN connectivity  
3. **Privacy implications** - All prompts leave the local network
4. **Cost tracking** - Per-token billing introduces economic concerns that weren't present with local inference

**Why do it this way:**
The most important thing about this project is showing off the power behind the protocol of ZeroconfAI. Not the client or server that runs it. So, we build the Ollama server and OpenRouter servers to show off to developers that finding ai services is really as simple as just using zeroconfAI.

## The code that I want to work on

## The Local Proxy Client Architecture

This is the component Adam was most excited about, and I think it's the most elegant part of the system.

**The Problem:**
Applications like Jan (an open-source ChatGPT alternative) run their own OpenAI-compatible servers (typically at `localhost:1337`). They expect to connect to a single, stable endpoint. But as you have seen in the code, ZeroconfAI is all about discovering multiple services that may come and go dynamically.

**The Solution: Reverse Proxy Pattern**

The `local_proxy_client` is a Python application that:

1. **Discovers** all available ZeroconfAI services on the network (both local Ollama instances and cloud-backed gateways)
2. **Exposes** a single, stable OpenAI-compatible HTTP endpoint (at `localhost:8080` or configurable)
3. **Routes** incoming requests intelligently based on:
   - Service availability (health checks)
   - Model capability matching (if someone wants an image then they should get an image model)
   - Cost optimization (prefer local over cloud when models are equivalent, shouldn't use thinking models on simple questions (of course deeming a question as simple is non trivial.))

**Architecture Specifics:**

The proxy maintains an in-memory registry of discovered services with their capabilities. When a request arrives at `/v1/chat/completions`, the proxy:

1. Parses the requested model from the request body
2. Queries the registry for services advertising that model
3. Filters to currently-healthy services
4. Selects a service based on the routing from before.
5. Forwards the request with proper header rewriting
6. Streams the response back to the client

**Why local proxy Matters:**

Applications can point to the proxy without knowing anything about ZeroconfAI. Jan, for instance, can be configured to use `http://localhost:8080` as its backend. The proxy handles all the complexity of service discovery, health monitoring, and intelligent routing.

This creates a powerful abstraction: developers write against the standard OpenAI API, users get automatic discovery and failover of available AI services, and the whole system adapts dynamically to changing network topology.

**Implementation Decisions:**

I initially considered writing this in C++ to showcase low-level systems programming (memory management, pointer manipulation, native DNS libraries). After spending time with the C++ implementation—learning about header files, mutexes, and RAII—I realized I was optimizing the wrong thing. You can find these files in cpp attempt if you look in the references/Cpp_attempt folder.

**I'm switching back to Python.** 
The implementation will be cleaner, more maintainable, and easier for other developers to understand when they're evaluating whether to adopt ZeroconfAI. The ~1ms overhead of Python vs C++ is meaningless when the upstream inference request takes 500ms-5s.

## Current Status and Next Steps

local_proxy_server.py was generated with AI and needs to be refractored to fit the theme of the rest of my project, all while maintaining the goal it was always supposed to serve. 

## Reminding you why this Matters

The bigger vision here is reducing friction for AI feature adoption. Right now, adding LLM capabilities to an open-source project means:
1. Choosing a provider (lock-in)
2. Handling API keys (security, cost)  
3. Building subscription infrastructure if you want to monetize
4. Dealing with user complaints about mandatory cloud dependencies

ZeroconfAI inverts this: applications declare "I can use AI if available" and users provide their own inference, whether that's a local Ollama instance, a shared household Raspberry Pi gateway, or even their company's on-premise LLM infrastructure.

The local_proxy_client is the piece that makes this practical for existing applications—they don't need to adopt the ZeroconfAI protocol directly, they just point at the proxy and everything works.
