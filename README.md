# Saturn: Zero-configuration AI Service Discovery

*Are you tired of managing API keys for every single app that wants to use AI?*

*Does your open-source project need AI features but you don't want to become a SaaS company?*

*Have you ever thought "Why can't AI just work like printers do?"*

## Meet Sarah, Open Source Developer

Sarah maintains a photo organization app. Users keep asking for AI features - auto-tagging, smart search, caption generation. 

Her options suck:
- Option 1: Make every user get their own API keys (*47-step setup guide, anyone?*)
- Option 2: Pay for everyone's AI usage (*goodbye, rent money*)
- Option 3: Just... don't add AI features (*sad trombone*)

**But what if there was another way?**

## Now Meet Derek, The Home IT Wizard

Derek already pays for OpenRouter/Claude/OpenAI. He uses it for work, for fun, for randomly inserting references to _Hollow Knight_ into his code.

He thinks: "I'm already paying for this. Why can't my family's apps just... use it?"

So Derek runs our script on a Raspberry Pi. Now every app on his home network can discover and use AI. No API keys. No configuration. It just works.

**But wait, there's more!** Derek's tech-savvy neighbor also runs Ollama locally. Derek's apps automatically discover BOTH services and pick the best one. If OpenRouter goes down? Seamless failover to local Ollama. It's like RAID, but for AI.


## What's In This Repo

### The Servers (`servers/`)

**OpenRouter Server (`servers/openrouter_server.py`)**
- FastAPI server that proxies to OpenRouter API (access to 200+ AI models)
- **Dynamic model discovery** - automatically fetches and caches available models every hour
- Supports all OpenRouter models: Claude, GPT-4, Gemini, Llama, and more
- Includes special "openrouter/auto" model for intelligent routing
- Full streaming support for real-time responses
- Automatic priority negotiation (defaults to priority 50)


**Ollama Server (`servers/ollama_server.py`)**
- Proxies to your local Ollama installation
- Automatically discovers whatever models you have installed
- Zero external API costs - it's all running on your hardware
- Perfect for offline work or privacy-sensitive tasks
- Converts Ollama's native format to OpenAI-compatible responses

**Fallback Server (`servers/fallback_server.py`)**
- The world's most honest server
- Model literally named "dont_pick_me"
- If you actually pick it, it roasts you
- Great for testing client failover logic
- Contains the condensed wisdom of ignoring clear warnings

### The Clients (`clients/`)

**Simple Chat Client (`clients/simple_chat_client.py`)**
- Bare-bones example of service discovery
- Automatically finds the highest-priority service
- Basic chat loop with history
- Under 100 lines - read it to understand the protocol

**Local Proxy Client (`clients/local_proxy_client.py`)**
- Bridge for third-party apps without native Saturn support (like Jan)
- Full-featured client with health monitoring
- Discovers ALL services on your network
- Automatic failover if a service goes down
- Priority-based selection (use local before cloud, or configure your own preferences)
- Maintains chat history across provider switches
- Note: For Open WebUI, use the native `owui_saturn.py` function instead

**File Upload Client (`clients/file_upload_client.py`)**
- Advanced multimodal client supporting file uploads
- Handles text files, images (PNG, JPEG, GIF, WebP), and PDFs
- Token tracking and cost estimation
- Automatic MIME type detection
- Perfect for "analyze this image" or "summarize this document" use cases

### Open WebUI Integration (`owui_saturn.py`)

**The easiest way to use Saturn with a polished web interface**

The `owui_saturn.py` file implements a service discovery pipe for Open WebUI that automatically discovers and connects to AI model services advertised on the local network. This pipe enables Open WebUI to seamlessly integrate with multiple LLM providers without manual configuration.

- **SaturnDiscovery**: Uses the `dns-sd` command-line tool to browse for services advertising the `_saturn._tcp` service type
- **Pipe Class**: Implements the Open WebUI pipe interface with configurable valves for discovery timeout, failover behavior, cache TTL, and request timeout

**Installation:**

1. Install Open WebUI (either desktop app or server):
   - Desktop: https://github.com/open-webui/desktop
   - Server: https://github.com/open-webui/open-webui

2. Add the Saturn function:
   - Go to Settings → Admin Settings → Functions
   - Click "+" → "Discover a Function"
   - Search for "Saturn" and install
   - Alternatively, copy the code from `owui_saturn.py` and paste into a new function

3. Enable the function and refresh Open WebUI

4. Start a Saturn server on your network

5. Saturn models will appear in your model selector with the `SATURN/` prefix

### VLC Extension (`vlc_extension/`)

**Wait, VLC? Like, the media player?**

Yes! Derek thought: "What if I could ask AI questions about the movie I'm watching?"

So now you can. The VLC extension comes in two flavors:

**Saturn Chat** - Interactive AI chat about your media
- Ask questions about the content you're watching
- Get context-aware responses (AI knows what media file you're playing)
- Automatically discovers AI services on your network using DNS-SD
- Switch between services and models right in the UI

**Saturn Roast** - Entertainment roasting of your media taste
- Get witty, sarcastic AI commentary about what you're watching
- Analyzes your media (title, artist, album, genre)
- Lighthearted entertainment powered by your Saturn AI services

Both extensions use a bundled Python bridge that discovers Saturn services via DNS-SD (same mechanism as the Python clients). No separate Python installation needed!

**Installation:**
Copy the entire `vlc_extension/` directory to your VLC extensions folder:
```bash
# Linux
~/.local/share/vlc/lua/extensions/

# macOS
~/Library/Application Support/org.videolan.vlc/lua/extensions/

# Windows
%APPDATA%\vlc\lua\extensions\
```

Then in VLC:
- **Chat**: View → Extensions → Saturn Chat
- **Roast**: View → Extensions → Saturn Roast Extension

**Features:**
- Automatic service discovery on your local network
- Model aggregation from all discovered Saturn services
- Priority-based routing with automatic failover
- Configurable settings (discovery timeout, cache TTL, request timeout)
- Full streaming support for real-time responses

## Quick Start

### Server Setup

1. **Set up your environment:**
```bash
git clone https://github.com/jperrello/Saturn.git
cd Saturn

# Basic dependencies (required for all servers/clients)
pip install fastapi uvicorn zeroconf python-dotenv requests pydantic

# Optional: For file upload client with multimodal support
pip install tiktoken Pillow
```

2. **For OpenRouter Server (access to 200+ AI models):**
```bash
echo "OPENROUTER_API_KEY=your-key-here" > .env
echo "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions" >> .env

python servers/openrouter_server.py
python servers/openrouter_server.py --priority 10
python servers/openrouter_server.py --port 8081 --priority 5
```

3. **For Ollama Server (requires Ollama running locally):**
```bash
python servers/ollama_server.py
python servers/ollama_server.py --priority 100
```

4. **For Fallback Server (for testing or amusement):**
```bash
python servers/fallback_server.py --priority 999
```
Alternatively, you can create your own server! Follow the logic in the servers/ folder, and announce a service with:
```bash
dns-sd -R "<name>" "_saturn._tcp" "local" 8081 "version=1.0" "api=<api>" "priority=50"
```

### Priority System

Lower numbers = higher priority. Clients pick the lowest-priority service available.

Example setup:
- Local Ollama: priority 10 (use this first - it's free and private)
- OpenRouter: priority 50 (use if Ollama is down)
- Fallback server: priority 999 (only if you're truly desperate)

 If you try to start two services with the same priority, the second one automatically increments until it finds an available slot. No conflicts, no angry servers fighting over a port number.

### Client Usage

**Simple client (basic chat):**
```bash
python clients/simple_chat_client.py
```

**Advanced client with failover:**
```bash
python clients/local_proxy_client.py
```

**File upload client (multimodal):**
```bash
python clients/file_upload_client.py
```

**Using clients in your code:**
```python
from clients.local_proxy_client import ServiceManager, SaturnClient

manager = ServiceManager()
time.sleep(2)  # Give it a moment to discover services

for url, name in manager.items():
    client = SaturnClient(manager, url)
    break

response = client.chat("What's the meaning of life?")
print(response)
```

## Example network

- Derek's Raspberry Pi: Running OpenRouter server (priority 50)
- Derek's gaming PC: Running Ollama server (priority 10)
- Derek's definitely-not-overkill homelab: Running fallback server (priority 999)

All of Derek's family's apps automatically use the gaming PC first (priority 10), fall back to the Raspberry Pi if it's busy (priority 50), and... well, hopefully never hit the fallback server (priority 999).

## Architecture

**Service Discovery**: Saturn uses mDNS (Multicast DNS) for zero-configuration service discovery
- **Service Type**: `_saturn._tcp.local.`
- **Discovery Methods**:
  - DNS-SD subprocess commands (`dns-sd -B`, `dns-sd -L`) - used by OpenRouter/Ollama servers, simple_chat_client, local_proxy_client, and VLC bridge
  - Python zeroconf library - used by fallback_server and file_upload_client
  - Both methods are fully compatible and discover the same services

**Service Registration** (Servers):
- Each server registers itself via mDNS when started
- TXT records include: version, API type, features, and priority

**Service Discovery** (Clients):
- Continuous background browsing for Saturn services
- Health monitoring and model discovery
- Priority-based selection

**API Endpoints**:
- `/v1/health` - Check if service is alive
- `/v1/models` - List available models
- `/v1/chat/completions` - OpenAI-compatible chat endpoint

**Request Format**:
```json
{
  "model": "model-name",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

__All servers speak OpenAI-compatible API.__ Whether you're hitting OpenRouter, Ollama, or even the sarcastic fallback server, the request/response format is identical. This means your client code works with ANY Saturn server without modification.


## FAQ

**"Wait, I can mix cloud and local AI?"**
Yes! Run Ollama locally for free/private stuff, plus OpenRouter for cloud access to 200+ models. Clients pick the best one automatically.

**"What if multiple people try to use my Ollama at once?"**
Set Ollama to lower priority (higher number). Clients will prefer your cloud services when local is busy.

**"Is this secure?"**
It's as secure as your home network. If you trust devices on your WiFi, you can trust this. Want more security? Run it on a separate VLAN or add authentication (PRs welcome).

**"What about costs?"**
Ollama server: Free (uses your hardware)
OpenRouter server: You pay for your own OpenRouter usage
Your whole network shares one account instead of everyone getting their own.

**"What's the VLC extension for?"**
Ever wanted to ask questions about the movie you're watching? Now you can. Saturn Chat lets you chat with AI while watching media, with full context awareness of what you're viewing. Saturn Roast provides entertainment by roasting your media taste with witty AI commentary. Both use the same DNS-SD discovery as other Saturn clients.

**"What about Open WebUI integration?"**
Open WebUI is a feature-rich web interface for AI chat. The Saturn function (`owui_saturn.py`) integrates directly with Open WebUI to provide automatic service discovery. Install it as a function in Open WebUI, and all your Saturn services will appear automatically in the model selector. No manual endpoint configuration needed.

**"Can I run ALL the servers?"**
Absolutely! Run one of each, give them different priorities, and let clients pick the best one. That's the whole point.

**"Why does the fallback server exist?"**
Mostly for laughs. Also great for testing client failover logic. Try it, you'll see.

**"What happens when Ollama is generating and someone else makes a request?"**
Depends on your Ollama configuration, but typically it'll queue. Or just run another server at higher priority as overflow.

---

Feel free to make a PR or reach out for any questions.