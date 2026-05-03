import multicastDns from "multicast-dns"
import { networkInterfaces } from "os"
import { spawn, type Subprocess } from "bun"

const SATURN_SERVICE = "_saturn._tcp.local"
const SCAN_MS = 3000
const CORS = { "Access-Control-Allow-Origin": "*" }
function adminPassword(): string {
  if (process.env.SATURN_ADMIN_PASSWORD) return process.env.SATURN_ADMIN_PASSWORD
  const generated = crypto.randomUUID().replace(/-/g, "").slice(0, 16)
  console.log("")
  console.log("  ┌─ Saturn admin password ─────────────────────────")
  console.log(`  │  ${generated}`)
  console.log("  │  (set SATURN_ADMIN_PASSWORD to override)")
  console.log("  └─────────────────────────────────────────────────")
  console.log("")
  return generated
}

const ADMIN_PASSWORD = adminPassword()
const HEALTH_INTERVAL = 20_000
const BREAKER_THRESHOLD = 3
const BREAKER_COOLDOWN = 30_000

interface Service {
  name: string
  host: string
  port: number
  status: "online" | "offline"
  priority: number
  deployment: string
  apiType: string
  models: string[]
}

interface Breaker {
  failures: number
  openedAt: number
}

// cache discovered services so chat can look them up
let cache: Service[] = []
const breakers = new Map<string, Breaker>()
const health = new Map<string, boolean>()

function breaker(name: string): Breaker {
  if (!breakers.has(name)) breakers.set(name, { failures: 0, openedAt: 0 })
  return breakers.get(name)!
}

function isOpen(b: Breaker): boolean {
  if (b.failures < BREAKER_THRESHOLD) return false
  if (Date.now() - b.openedAt > BREAKER_COOLDOWN) {
    b.failures = 0
    return false
  }
  return true
}

function recordFailure(name: string) {
  const b = breaker(name)
  b.failures++
  if (b.failures >= BREAKER_THRESHOLD) b.openedAt = Date.now()
}

function recordSuccess(name: string) {
  breaker(name).failures = 0
}

// background health polling
async function healthLoop() {
  while (true) {
    for (const svc of cache) {
      const base = `http://${svc.host}:${svc.port}`
      try {
        const res = await fetch(`${base}/v1/health`, { signal: AbortSignal.timeout(5000) })
        health.set(svc.name, res.ok)
      } catch {
        health.set(svc.name, false)
      }
    }
    await Bun.sleep(HEALTH_INTERVAL)
  }
}

// start health loop
healthLoop()

function lanIP(): string | null {
  const nets = networkInterfaces()
  for (const addrs of Object.values(nets)) {
    if (!addrs) continue
    for (const a of addrs) {
      if (a.family === "IPv4" && !a.internal) return a.address
    }
  }
  return null
}

// --- cloudflared tunnel ---
let tunnel: Subprocess | null = null
let tunnelUrl: string | null = null
let tunnelLog: string[] = []

async function startTunnel(port: number): Promise<string | null> {
  if (tunnel) return tunnelUrl

  tunnelUrl = null
  tunnelLog = []

  tunnel = spawn({
    cmd: ["cloudflared", "tunnel", "--url", `http://localhost:${port}`],
    stdout: "pipe",
    stderr: "pipe",
  })

  // cloudflared prints the URL to stderr
  const reader = tunnel.stderr.getReader()
  const decoder = new TextDecoder()
  const deadline = Date.now() + 30_000

  while (Date.now() < deadline) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value)
    tunnelLog.push(text)
    // look for the trycloudflare.com URL
    const match = text.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/)
    if (match) {
      tunnelUrl = match[0]
      // keep draining stderr in background so the pipe doesn't block
      ;(async () => {
        while (true) {
          const { done } = await reader.read()
          if (done) break
        }
      })()
      return tunnelUrl
    }
  }

  return null
}

function stopTunnel() {
  if (!tunnel) return
  tunnel.kill()
  tunnel = null
  tunnelUrl = null
  tunnelLog = []
}

function discover(): Promise<Service[]> {
  return new Promise((resolve) => {
    const found = new Map<string, Service>()
    const mdns = multicastDns()

    mdns.on("response", (response) => {
      const srvs = response.additionals?.filter((r) => r.type === "SRV") ?? []
      const txts = response.additionals?.filter((r) => r.type === "TXT") ?? []
      const answers = response.answers?.filter((r) => r.type === "SRV") ?? []

      for (const srv of [...srvs, ...answers]) {
        if (srv.type !== "SRV") continue
        const name = srv.name.replace(/\._saturn\._tcp\.local\.?$/, "")
        const data = srv.data as { target: string; port: number }
        const svc: Service = {
          name,
          host: data.target,
          port: data.port,
          status: "online",
          priority: 100,
          deployment: "network",
          apiType: "openai",
          models: [],
        }

        const txt = txts.find((t) => t.name === srv.name)
        if (txt && txt.type === "TXT") {
          const parts = (txt.data as Buffer[]).map((b) => b.toString())
          for (const p of parts) {
            const [k, ...rest] = p.split("=")
            const v = rest.join("=")
            if (k === "priority") svc.priority = parseInt(v) || 100
            if (k === "deployment") svc.deployment = v
            if (k === "api_type") svc.apiType = v
            if (k === "models") svc.models = v.split(",").filter(Boolean)
          }
        }

        found.set(name, svc)
      }
    })

    mdns.query({ questions: [{ name: SATURN_SERVICE, type: "PTR" }] })

    setTimeout(() => {
      mdns.destroy()
      const services = [...found.values()].sort((a, b) => a.priority - b.priority)
      cache = services
      resolve(services)
    }, SCAN_MS)
  })
}

// fetch models from a saturn service's OpenAI-compatible endpoint
async function models(svc: Service): Promise<{ id: string; owned_by?: string }[]> {
  const base = `http://${svc.host}:${svc.port}`
  try {
    const res = await fetch(`${base}/v1/models`, { signal: AbortSignal.timeout(5000) })
    if (!res.ok) return []
    const json = await res.json()
    return json.data ?? []
  } catch {
    return []
  }
}

// proxy streaming chat completions — same pattern as omlx saturn adapter
// tries candidates in priority order, streams SSE back to client
async function proxy(urls: string[], payload: any): Promise<Response> {
  for (const base of urls) {
    try {
      const res = await fetch(`${base}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(60000),
      })
      if (!res.ok) continue
      if (!res.body) continue

      // pipe the upstream SSE stream directly to the client
      return new Response(res.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
          ...CORS,
        },
      })
    } catch {
      continue
    }
  }
  return Response.json(
    { error: "All upstream services failed" },
    { status: 502, headers: CORS }
  )
}

const server = Bun.serve({
  port: 3000,
  async fetch(req) {
    const url = new URL(req.url)

    // CORS preflight
    if (req.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          ...CORS,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
          "Access-Control-Expose-Headers": "X-Saturn-Service, X-Saturn-Model",
        },
      })
    }

    if (url.pathname === "/api/admin/auth" && req.method === "POST") {
      const body = await req.json()
      if (body.password !== ADMIN_PASSWORD) {
        return Response.json({ detail: "Invalid password" }, { status: 401, headers: CORS })
      }
      return Response.json({ ok: true }, { headers: CORS })
    }

    if (url.pathname === "/api/discover") {
      const services = await discover()
      return Response.json(services, { headers: CORS })
    }

    // fetch models from a specific service
    if (url.pathname === "/api/models") {
      const name = url.searchParams.get("service")
      const svc = cache.find((s) => s.name === name)
      if (!svc) return Response.json([], { headers: CORS })
      const list = await models(svc)
      return Response.json(list, { headers: CORS })
    }

    // brutus auto-routed chat — picks best healthy backend automatically
    if (url.pathname === "/api/system/chat" && req.method === "POST") {
      const body = await req.json()
      const { messages } = body

      // pick healthy, non-tripped services in priority order
      let candidates = cache
        .filter((s) => s.status === "online")
        .filter((s) => !isOpen(breaker(s.name)))
        .filter((s) => health.get(s.name) !== false)
        .sort((a, b) => a.priority - b.priority)

      // fallback: skip health filter if everything looks dead
      if (candidates.length === 0) {
        candidates = cache
          .filter((s) => s.status === "online")
          .filter((s) => !isOpen(breaker(s.name)))
          .sort((a, b) => a.priority - b.priority)
      }

      if (candidates.length === 0) {
        return Response.json(
          { error: "No healthy backends available. Run discovery first." },
          { status: 502, headers: CORS }
        )
      }

      // try each candidate with circuit breaker tracking
      for (const svc of candidates) {
        const base = `http://${svc.host}:${svc.port}`
        // resolve model — use first from service, or fetch from endpoint
        let model = svc.models[0]
        if (!model) {
          try {
            const mres = await fetch(`${base}/v1/models`, { signal: AbortSignal.timeout(5000) })
            const mj = await mres.json() as any
            model = mj.data?.[0]?.id
          } catch { /* skip */ }
        }
        if (!model) continue

        try {
          const res = await fetch(`${base}/v1/chat/completions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model, messages, stream: true }),
            signal: AbortSignal.timeout(60000),
          })
          if (!res.ok || !res.body) {
            recordFailure(svc.name)
            continue
          }
          recordSuccess(svc.name)
          return new Response(res.body, {
            headers: {
              "Content-Type": "text/event-stream",
              "Cache-Control": "no-cache",
              Connection: "keep-alive",
              "X-Saturn-Service": svc.name,
              "X-Saturn-Model": model,
              "Access-Control-Expose-Headers": "X-Saturn-Service, X-Saturn-Model",
              ...CORS,
            },
          })
        } catch {
          recordFailure(svc.name)
          continue
        }
      }

      return Response.json(
        { error: "All backends failed" },
        { status: 502, headers: CORS }
      )
    }

    // brutus URL for QR code — returns tunnel URL or LAN fallback
    if (url.pathname === "/api/system/url") {
      if (tunnelUrl) {
        return Response.json({ url: tunnelUrl, mode: "tunnel" }, { headers: CORS })
      }
      const ip = lanIP()
      const port = server.port
      const brutusUrl = ip ? `http://${ip}:${port}` : null
      return Response.json({ url: brutusUrl, mode: "lan" }, { headers: CORS })
    }

    // start cloudflared tunnel
    if (url.pathname === "/api/system/tunnel/start" && req.method === "POST") {
      if (tunnelUrl) {
        return Response.json({ url: tunnelUrl, status: "running" }, { headers: CORS })
      }
      const url2 = await startTunnel(server.port)
      if (url2) {
        return Response.json({ url: url2, status: "running" }, { headers: CORS })
      }
      return Response.json(
        { error: "Tunnel failed to start. Is cloudflared installed?", log: tunnelLog.join("") },
        { status: 500, headers: CORS }
      )
    }

    // stop cloudflared tunnel
    if (url.pathname === "/api/system/tunnel/stop" && req.method === "POST") {
      stopTunnel()
      return Response.json({ status: "stopped" }, { headers: CORS })
    }

    // tunnel status
    if (url.pathname === "/api/system/tunnel/status") {
      return Response.json(
        { url: tunnelUrl, status: tunnel ? "running" : "stopped" },
        { headers: CORS }
      )
    }

    // proxy chat completions — streams SSE from the target service
    if (url.pathname === "/api/chat" && req.method === "POST") {
      const body = await req.json()
      const { service: name, model, messages } = body

      // find candidate services, requested service first, then by priority
      const candidates = cache
        .filter((s) => s.status === "online")
        .sort((a, b) => {
          if (a.name === name) return -1
          if (b.name === name) return 1
          return a.priority - b.priority
        })

      if (candidates.length === 0) {
        return Response.json(
          { error: "No services available. Run discovery first." },
          { status: 400, headers: CORS }
        )
      }

      const urls = candidates.map((s) => `http://${s.host}:${s.port}`)
      return proxy(urls, { model, messages, stream: true })
    }

    // dev-mode stubs for endpoints only the python server fully implements;
    // returning empty data keeps the UI quiet instead of throwing on 404.
    if (url.pathname === "/api/services") {
      return Response.json([], { headers: CORS })
    }
    if (url.pathname === "/api/rate-limit/status") {
      return Response.json({ rpm: { limit: 60, remaining: 60 } }, { headers: CORS })
    }
    if (url.pathname === "/api/admin/config") {
      if (req.method === "POST") return Response.json({ ok: true }, { headers: CORS })
      return Response.json({ model_filter: "" }, { headers: CORS })
    }
    if (url.pathname === "/api/usage" || url.pathname === "/api/usage/history") {
      return Response.json({ requests: 0, tokens_in: 0, tokens_out: 0, history: [] }, { headers: CORS })
    }
    if (url.pathname === "/api/usage/report") {
      return Response.json({ ok: true }, { headers: CORS })
    }

    // openai-compatible aliases — saturn is the proxy, /v1/* mirrors /api/proxy/*
    if (url.pathname === "/v1/health") {
      return Response.json({ status: "ok" }, { headers: CORS })
    }
    if (url.pathname === "/v1/models") {
      const ids = new Set<string>()
      for (const svc of cache) {
        if (svc.status !== "online") continue
        for (const m of svc.models || []) ids.add(m)
      }
      const data = [...ids].map((id) => ({ id, object: "model" }))
      return Response.json({ object: "list", data }, { headers: CORS })
    }

    // serve static files
    let path = url.pathname === "/" ? "/index.html" : url.pathname
    const file = Bun.file(import.meta.dir + path)
    if (await file.exists()) return new Response(file)
    return new Response("Not found", { status: 404 })
  },
})

console.log(`Saturn Web UI → http://localhost:${server.port}`)
