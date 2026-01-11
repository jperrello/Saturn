# Saturn Design Fiction

These stories illustrate the problems Saturn solves and the people who benefit from it.

---

## Meet Sarah, Open Source Developer

Sarah maintains a photo organization app. Users keep asking for AI features - auto-tagging, smart search, caption generation.

Her options suck:
- **Option 1:** Make every user get their own API keys (*47-step setup guide, anyone?*)
- **Option 2:** Pay for everyone's AI usage (*goodbye, rent money*)
- **Option 3:** Just... don't add AI features (*sad trombone*)

**But what if there was another way?**

With Saturn, Sarah's app can discover AI services on the local network automatically. No API key distribution. No SaaS billing nightmare. Users on networks with Saturn servers just... get AI features. Zero configuration required.

---

## Meet Derek, The Home IT Wizard

Derek already pays for OpenRouter/Claude/OpenAI. He uses it for work, for fun, for randomly inserting references to _Hollow Knight_ into his code.

He thinks: "I'm already paying for this. Why can't my family's apps just... use it?"

So Derek runs a Saturn server on a Raspberry Pi. Now every app on his home network can discover and use AI. No API keys. No configuration. It just works.

**Derek's setup:**
- Gaming PC: Running Ollama server (priority 10) - fast, free, private
- Raspberry Pi: Running OpenRouter server (priority 50) - cloud fallback
- The definitely-not-overkill homelab: Running fallback server (priority 999) - for laughs

All of Derek's family's apps automatically use the gaming PC first, fall back to the Pi if it's busy, and... hopefully never hit the fallback server.

---

## Meet Jordan, The Developer Who Learned Fear

Derek's setup is elegant. Sarah's users are happy. But there's one person who's nervous: Jordan.

Jordan's team had The Incident last year. An intern's laptop got stolen. With it: API keys hard-coded in config files, Slack DMs, browser bookmarks, and one very embarrassing sticky note.

The 2 AM response:
- Emergency key rotation across every system
- Security audit (keys found in 47 different places, including one in a commented-out test)
- New workflow: Weekly manual rotation, separate keys per person/device/environment
- Jordan's new title: "Person Who Worries About Credentials Now"

This workflow is secure. It's also a full-time job.

**Jordan's concern about Saturn:** "So Derek just... gives everyone the same API key? That's network-level access, but those keys live forever. What happens when someone leaves the network? When a laptop gets stolen? When an intern commits secrets to GitHub?"

### The Beacon Solution

At a conference, someone mentions Saturn Beacons. Jordan's response: "Hard pass."

"Network-based credentials? That's just shared WiFi passwords with extra steps."

**But beacons aren't WiFi passwords. Here's what they actually do:**

The beacon generates ephemeral JWTs from DeepInfra with a 10-minute expiration. It rotates them every 5 minutes. It broadcasts them via mDNS (local network only). Clients discover the beacon automatically, extract the current JWT, and use it to call AI APIs directly.

Laptop stolen? The key expires in less than 10 minutes. Employee leaves the company? They leave the network, credentials die automatically. No revocation lists. No emergency 2 AM rotations. No keys persisted in configs, DMs, or sticky notes.

Jordan runs a beacon on a Raspberry Pi in the server closet. Setup time: 5 minutes. Ongoing maintenance: zero. Security incidents since deployment: also zero.

**Jordan still worries about credentials. But now they worry significantly less.**

---

## The Common Thread

Sarah, Derek, and Jordan have different problems:
- Sarah needs to add AI to her app without becoming a SaaS company
- Derek wants to share his AI subscriptions with his family
- Jordan needs credential security without the operational nightmare

Saturn solves all three. The protocol is simple: services announce themselves on the network, clients discover them automatically. The implementation is flexible: run Ollama for free/private AI, OpenRouter for cloud access, or beacons for ephemeral credentials.

**The result?** AI that works like printers do. You don't configure your printer's IP address. You don't paste API keys into every app that wants to print. You just... print.

Saturn makes AI work the same way.

---

*For technical details, see the [main README](../README.md). For beacon-specific documentation, see [beacons/README.md](../beacons/README.md).*
