# Design Fiction 2: Adam's GPU Bailout

**Setting:** Joey has been burning through cloud credits running Gas Town for a large refactoring project. He's spent $300 in three days. He visits Adam, his advisor, who casually mentions he just got an RTX 5090 with 32GB VRAM and has Ollama running with Llama 3.3 70B quantized.

---

Joey's laptop connects to Adam's WiFi. Thirty seconds later, his terminal shows:

```
🪐 Saturn Rings: New service discovered
   └─ adams-workstation._rings._tcp.local
      ├─ models: llama-3.3-70b-q4, deepseek-r1-q4, mixtral-8x22b
      ├─ context: 32768 | cost: free
      ├─ priority: 10
      └─ mcp: 2025-11-25
```

Joey has been using Claude Sonnet for everything—reasoning steps, code generation, test writing. But looking at Adam's Ollama setup, he realizes the bulk work doesn't need cloud. A 70B model running locally is more than capable.

He opens his Gas Town config and adds a routing rule:

```toml
[routing.prefer-local]
enabled = true
services = ["*._rings._tcp.local"]
cost-tier = "free"
tasks = ["code-generation", "test-writing", "documentation"]

[routing.cloud-required]
models = ["claude-3-opus", "claude-3-sonnet"]
tasks = ["architecture", "security-review", "complex-reasoning"]
```

He restarts his convoy. The behavior changes immediately. The Mayor shows:

```
Convoy "refactor-auth" - Routing Status
├─ code-gen tasks → adams-workstation (llama-3.3-70b-q4) [free]
├─ test-writing → adams-workstation (llama-3.3-70b-q4) [free]
├─ architecture → cloud (claude-3-sonnet) [metered]
└─ Active session: sticky to adams-workstation for current task
```

Simple code generation flows to Adam's Ollama. Complex reasoning still hits the cloud. The cost tracker shows the difference in real-time:

```
📊 Cost Analysis - Convoy "refactor-auth"
├─ Before routing: $12.40/hour (100% cloud)
├─ After routing:  $2.10/hour (17% cloud, 83% local)
├─ Session tokens: 145k local, 31k cloud
└─ Projected savings: $247 over remaining work
```

Joey says to Adam: "Your GPU is saving me hundreds of dollars right now."

Adam responds: "Haha, I can see the utilization spike. Want me to spin up a second model?"

Adam runs:
```bash
ollama serve --model deepseek-coder-33b --port 11435
saturn-rings advertise --name "adams-coder" --port 11435 --models deepseek-coder-33b --cost free --priority 15
```

His Saturn Rings advertiser broadcasts the new service. Joey's Gas Town picks it up within seconds—no configuration, no restart:

```
🪐 Saturn Rings: New service discovered
   └─ adams-coder._rings._tcp.local
      ├─ models: deepseek-coder-33b
      ├─ context: 16384 | cost: free
      ├─ priority: 15
      └─ mcp: 2025-11-25

🔄 Router: adams-coder added to pool
   └─ Code-optimized model detected
   └─ Assigning to: code-generation tasks
```

The coding-specific model starts handling implementation work while Llama 3.3 handles higher-level reasoning. Joey's convoy self-optimizes:

```
Convoy "refactor-auth" - Updated Routing
├─ reasoning → adams-workstation (llama-3.3-70b-q4) [free]
├─ implementation → adams-coder (deepseek-coder-33b) [free]
├─ architecture → cloud (claude-3-sonnet) [metered]
└─ Cloud usage dropped to 8%
```

By the end of the session, Joey's spent $8 instead of the $100+ he would have burned through on cloud alone.

When he packs up to leave, the Mayor warns:

```
⚠️  Leaving Saturn Rings network
    └─ 2 local services will become unavailable
    └─ Current task (test-writing) will complete on adams-workstation
    └─ Next task will route to cloud fallback

    [Continue current task?] [Switch to cloud now?]
```

Joey lets the current task finish—sticky sessions mean no mid-task disruption. Then Gas Town gracefully falls back to cloud inference. The routing rules persist, ready for the next local provider it discovers.

At home later, Joey runs:

```bash
saturn-rings discover
```

```
🪐 Saturn Rings: 0 services found
   └─ No local AI services on this network
   └─ Routing will use cloud fallback
```

He makes a note to set up his own Ollama. Maybe he'll advertise it via Saturn Rings so his roommates can use it too. One developer, zero configuration—that's the deal.

---

**What This Fiction Demonstrates:**

1. **Instant discovery**: Joey's laptop detected Adam's Ollama within 30 seconds of joining WiFi
2. **Zero configuration**: No IP addresses, no API keys, no manual setup
3. **Cost-tier routing**: Free local services preferred over metered cloud for appropriate tasks
4. **Sticky sessions**: No mid-task disruption when routing changes
5. **Dynamic service addition**: New services appear instantly without client restart
6. **Graceful degradation**: When leaving the network, fallback to cloud is seamless
7. **Priority-based selection**: Lower priority numbers = higher preference
8. **Real cost savings**: $100+ → $8 is transformative for individual developers
