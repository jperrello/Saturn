# Saturn AI SDK Provider — Testing Guide

> **Purpose**: Step-by-step instructions for testing the Saturn AI SDK provider with real services.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Option A: OpenCode Integration Test](#2-option-a-opencode-integration-test)
3. [Option B: Web Demo Fallback](#3-option-b-web-demo-fallback)
4. [Appendix: npm link Explained](#appendix-npm-link-explained)

---

## 1. Prerequisites

### Environment Setup

```bash
# Ensure you have these installed
node --version   # v18+ required
python --version # Python 3.8+ for Saturn server
```

### Environment Variables

Create a `.env` file in the `saturn/` directory:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
```

### Build the SDK

```bash
cd ai-sdk-provider-saturn/upstream
npm install
npm run build
```

---

## 2. Option A: OpenCode Integration Test

This is the preferred test — it proves the SDK works in a real AI application.

### Step 1: Start the Saturn Server

The Python `openrouter_server.py` acts as a local proxy that:
- Advertises itself via mDNS (`_saturn._tcp.local`)
- Proxies requests to OpenRouter
- Exposes all OpenRouter models

```bash
cd Saturn
python -m saturn.openrouter_server --priority 10
```

You should see:
```
Starting OpenRouter proxy on 0.0.0.0:8080 with priority 10
Registered OpenRouter on _saturn._tcp.local. at port 8080
```

Keep this terminal running.

### Step 2: Link the SDK Locally

`npm link` creates a symbolic link so other projects can use your local code without publishing to npm.

```bash
cd ai-sdk-provider-saturn/upstream
npm link
```

This registers `ai-sdk-provider-saturn` globally on your machine.

### Step 3: Clone and Set Up OpenCode

```bash
# Clone OpenCode
git clone https://github.com/anomalyco/opencode
cd opencode

# Install dependencies
npm install

# Link to your local Saturn SDK
npm link ai-sdk-provider-saturn
```

### Step 4: Add Saturn Provider to OpenCode

Find OpenCode's provider configuration (likely in `packages/opencode/src/provider/`).

Add Saturn as a provider:

```typescript
import { createSaturn } from 'ai-sdk-provider-saturn';

// Add to BUNDLED_PROVIDERS or equivalent
{
  id: 'saturn',
  name: 'Saturn (Network)',
  
  createProvider: () => {
    return createSaturn({ 
      discoveryTimeout: 5000,
      logLevel: 'info'
    });
  },
  
  // Saturn discovers models dynamically
  models: async () => {
    const saturn = createSaturn();
    await new Promise(r => setTimeout(r, 3000)); // Wait for discovery
    const services = saturn.getDiscovery().getAllServices();
    saturn.destroy();
    return services.flatMap(s => s.models);
  }
}
```

### Step 5: Run OpenCode

```bash
npm run dev
```

Then:
1. Open OpenCode in your browser
2. Go to Settings → Provider
3. Select "Saturn (Network)"
4. Choose a model (e.g., `openai/gpt-4o-mini`)
5. Start chatting

### Expected Behavior

- OpenCode discovers the Python Saturn server
- Model list populates from OpenRouter's catalog
- Chat requests route through Saturn → OpenRouter
- You should see logs in the Python server terminal

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "No Saturn services found" | Ensure Python server is running, check firewall for mDNS (port 5353 UDP) |
| Models not loading | Wait longer for discovery, or increase `discoveryTimeout` |
| 401 errors | Check your `OPENROUTER_API_KEY` is valid |
| npm link not working | Run `npm link` in upstream/, then `npm link ai-sdk-provider-saturn` in opencode/ |

---

## 3. Option B: Web Demo Fallback

If OpenCode integration is problematic, build a simple web demo instead.

### Create the Demo

Create `upstream/examples/web-demo/server.ts`:

```typescript
import { createServer } from 'http';
import { createSaturn } from '../../src/index.js';
import { streamText } from 'ai';

const saturn = createSaturn({ logLevel: 'debug' });

// Wait for discovery
await new Promise(r => setTimeout(r, 4000));

const server = createServer(async (req, res) => {
  // Serve HTML
  if (req.url === '/' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`
<!DOCTYPE html>
<html>
<head>
  <title>Saturn Demo</title>
  <style>
    body { font-family: system-ui; max-width: 800px; margin: 50px auto; padding: 20px; }
    #chat { border: 1px solid #ccc; padding: 20px; min-height: 300px; margin-bottom: 20px; }
    #input { width: 80%; padding: 10px; }
    button { padding: 10px 20px; }
    .user { color: blue; }
    .assistant { color: green; }
    .error { color: red; }
  </style>
</head>
<body>
  <h1>Saturn AI Demo</h1>
  <div id="services"></div>
  <div id="chat"></div>
  <input id="input" placeholder="Type a message..." />
  <button onclick="send()">Send</button>
  <script>
    // Fetch services on load
    fetch('/api/services')
      .then(r => r.json())
      .then(data => {
        document.getElementById('services').innerHTML = 
          '<p>Discovered: ' + data.services.map(s => s.name + ' (' + s.models.length + ' models)').join(', ') + '</p>';
      });

    async function send() {
      const input = document.getElementById('input');
      const chat = document.getElementById('chat');
      const message = input.value;
      input.value = '';
      
      chat.innerHTML += '<p class="user"><b>You:</b> ' + message + '</p>';
      chat.innerHTML += '<p class="assistant"><b>Saturn:</b> <span id="response"></span></p>';
      
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message })
        });
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          responseText += decoder.decode(value);
          document.getElementById('response').textContent = responseText;
        }
      } catch (e) {
        document.getElementById('response').innerHTML = '<span class="error">Error: ' + e.message + '</span>';
      }
    }
  </script>
</body>
</html>
    `);
    return;
  }

  // API: Get discovered services
  if (req.url === '/api/services' && req.method === 'GET') {
    const services = saturn.getDiscovery().getAllServices();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ 
      services: services.map(s => ({
        name: s.name,
        deployment: s.deployment,
        provider: s.provider,
        models: s.models
      }))
    }));
    return;
  }

  // API: Chat
  if (req.url === '/api/chat' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    const { message } = JSON.parse(body);

    res.writeHead(200, { 'Content-Type': 'text/plain' });

    try {
      const { textStream } = await streamText({
        model: saturn('openai/gpt-4o-mini'), // Or any OpenRouter model
        prompt: message,
        maxTokens: 500,
      });

      for await (const chunk of textStream) {
        res.write(chunk);
      }
      res.end();
    } catch (e) {
      res.end('Error: ' + e.message);
    }
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(3000, () => {
  console.log('Demo running at http://localhost:3000');
});
```

### Run the Demo

```bash
# Terminal 1: Saturn server
python -m saturn.openrouter_server

# Terminal 2: Web demo
cd ai-sdk-provider-saturn/upstream
npx tsx examples/web-demo/server.ts
```

Open http://localhost:3000 in your browser.

### What You'll See

1. The page shows discovered Saturn services
2. Type a message and click Send
3. Watch the response stream in real-time
4. Check both terminals for logs showing the full flow

---

## Appendix: npm link Explained

`npm link` is a two-step process for testing local packages:

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: npm link (in your package)                         │
│                                                             │
│  ai-sdk-provider-saturn/upstream/                           │
│         │                                                   │
│         └──► Creates global symlink                         │
│              ~/.npm-global/lib/node_modules/                │
│                  └── ai-sdk-provider-saturn → your folder   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Step 2: npm link ai-sdk-provider-saturn (in consumer)      │
│                                                             │
│  opencode/node_modules/                                     │
│         │                                                   │
│         └── ai-sdk-provider-saturn                          │
│                  │                                          │
│                  └──► Symlink to global → your folder       │
└─────────────────────────────────────────────────────────────┘
```

### Commands Reference

```bash
# Create global link (run in your package)
cd ai-sdk-provider-saturn/upstream
npm link

# Use the link (run in consuming project)
cd opencode
npm link ai-sdk-provider-saturn

# Remove the link
cd opencode
npm unlink ai-sdk-provider-saturn

# See all global links
npm ls -g --depth=0 --link=true
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "Cannot find module" | Forgot to run `npm link` in package | Run `npm link` in upstream/ first |
| Old code running | Didn't rebuild after changes | Run `npm run build` in upstream/ |
| TypeScript errors | Types not compiled | Run `npm run build` to generate .d.ts files |
| Permission errors (Linux/Mac) | Global npm needs sudo | Use `nvm` or fix npm permissions |

---

## Quick Reference

### Full Test Flow

```bash
# Terminal 1: Saturn server
cd Saturn
python -m saturn.openrouter_server

# Terminal 2: Build and link SDK
cd ai-sdk-provider-saturn/upstream
npm install && npm run build && npm link

# Terminal 3: OpenCode (Option A)
cd opencode
npm install && npm link ai-sdk-provider-saturn
npm run dev

# OR Terminal 3: Web Demo (Option B)
cd ai-sdk-provider-saturn/upstream
npx tsx examples/web-demo/server.ts
```

### Verify Discovery is Working

Quick test to confirm mDNS discovery:

```bash
cd ai-sdk-provider-saturn/upstream
npx tsx examples/discovery-info.ts
```

Should show your Python server with its models.
