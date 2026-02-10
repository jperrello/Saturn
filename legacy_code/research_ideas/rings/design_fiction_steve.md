# Design Fiction 1: Steve's Gas Town Empire

**Setting:** Steve has been running Gas Town for six months. His setup is battle-hardened—dozens of custom formulas, three rigs for different project types, and a Witness that's learned his coding patterns. His home network broadcasts AI services via Saturn Rings. Joey arrives to work on a frontend project.

---

Joey plugs his laptop into Steve's network. His terminal shows a notification:

```
🪐 Saturn Rings: 3 services discovered
   └─ steve-macpro._rings._tcp.local
      ├─ models: claude-3-sonnet, gpt-4o, llama-3.3-70b
      ├─ context: 128000 | cost: metered
      └─ mcp: 2025-11-25

   └─ steve-ollama._rings._tcp.local
      ├─ models: deepseek-coder-33b, mixtral-8x22b
      ├─ context: 32768 | cost: free
      └─ mcp: 2025-11-25

   └─ steve-gastown._convoy._tcp.local
      ├─ workers: 5 available | formulas: 23
      └─ federation: open (auth: psk)
```

"You've got Gas Town running?" Joey asks, surprised.

"Yeah. Want to use it?" Steve pulls up his Mayor session. Three convoys are active across two rigs, with eight polecats working in parallel on his side projects.

Joey has been meaning to set up Gas Town but hasn't had time. He opens his project—a React frontend with a gnarly state management problem. "Can your workers help with this?"

Steve types into the Mayor: `gt federation allow joey-mbp --scope=workers,formulas --track-usage`

Joey's terminal updates:

```
🤝 Federation established with steve-gastown
   └─ Auth: PSK verified
   └─ Importing formula registry (23 formulas, namespace: steve/)
   └─ Worker pool expanded: 5 remote slots
   └─ Usage tracking: enabled (metered settlement)
```

Joey runs `gt formula list` and sees Steve's catalog—`steve/shiny`, `steve/react-component`, `steve/refactor-safe`, `steve/test-first`. He picks `steve/react-component`:

```bash
gt convoy create "Fix state management" --formula=steve/react-component --remote
gt sling state-bug steve-gastown/react-rig
```

A polecat spins up on Steve's machine. Joey watches in his terminal as the worker analyzes his component tree, proposes a refactor to use Zustand, and implements it across twelve files.

The Mayor shows:
```
Convoy "state-bug" routing:
├─ reasoning tasks → steve-macpro (claude-3-sonnet) [metered]
├─ code generation → steve-ollama (deepseek-coder-33b) [free]
└─ Usage so far: 42k tokens ($0.13 metered + $0.00 local)
```

Steve's setup automatically routes expensive reasoning to his OpenRouter proxy while pushing bulk code generation to his local Ollama. Joey's metered usage is being tracked for later settlement—probably a Venmo request at the end of the month, or maybe Steve will just wave it off.

When Joey leaves, he runs:

```bash
gt federation export state-bug --format=molecule
```

He gets a molecule digest—a complete record of the work done: git commits, agent execution trace, formula configuration, token usage. When Joey eventually sets up his own Gas Town, he can import this molecule to bootstrap his Witness with knowledge of how the state-bug was solved.

```
📦 Molecule exported: state-bug-2026-01-03.molecule
   └─ 12 files modified, 3 commits
   └─ Formula used: steve/react-component
   └─ Total tokens: 67k (reasoning: 23k, generation: 44k)
   └─ Estimated cost: $0.21 (pending settlement with steve-gastown)
```

Joey checks his Saturn Rings dashboard later:

```
📊 Federation Usage Summary
   └─ steve-gastown: $0.21 pending
   └─ Settlement: Venmo @steveyegge or mark as gift
```

He Venmos Steve $1 with the note "gas money" and marks the debt settled. The metered tracking worked—no surprise bills, no awkwardness, just clear accounting between friends.

---

**What This Fiction Demonstrates:**

1. **Zero-configuration discovery**: Joey plugged in and immediately saw Steve's AI services via `_rings._tcp`
2. **MCP compatibility**: All services advertise their MCP version, enabling standard protocol interaction
3. **Federation with tracking**: Joey used Steve's workers with explicit usage metering
4. **Namespace prefixes**: Steve's formulas appear as `steve/` to avoid conflicts with Joey's future formulas
5. **Intelligent routing**: Gas Town automatically routed reasoning vs generation tasks to appropriate backends
6. **Molecule portability**: The work record exports cleanly for future use
7. **Gift economy with accountability**: Metered tracking enables settlement without forcing formal billing infrastructure
