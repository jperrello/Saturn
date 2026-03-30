import {
  extract, always, now, next, eventually,
  actions, weighted, strings, integers, from,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// test the Start tab: server panel, config form, start/stop lifecycle

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// --- extractors ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

const serverPanelVisible = extract((state) => {
  const panel = state.document.getElementById("server-panel")
  return panel ? !panel.classList.contains("hidden") : false
})

const configPageVisible = extract((state) => {
  const page = state.document.getElementById("config-page")
  return page ? !page.classList.contains("hidden") : false
})

const passwordGateVisible = extract((state) => {
  const gate = state.document.getElementById("password-gate")
  return gate ? !gate.classList.contains("hidden") : false
})

const serverCount = extract((state) => {
  const list = state.document.getElementById("server-list")
  if (!list) return 0
  const items = list.querySelectorAll(".checklist-item")
  // exclude the "No services configured" placeholder
  const first = items[0]?.textContent?.trim() ?? ""
  if (first.includes("No services configured")) return 0
  return items.length
})

const runningCount = extract((state) => {
  const badges = state.document.querySelectorAll(".status-up")
  return badges.length
})

const stoppedCount = extract((state) => {
  const badges = state.document.querySelectorAll(".status-down")
  return badges.length
})

// config form state
const cfgDeployment = extract((state) => {
  const sel = state.document.getElementById("cfg-deployment") as HTMLSelectElement | null
  return sel?.value ?? null
})

const cloudFieldsVisible = extract((state) => {
  const el = state.document.getElementById("cloud-fields")
  return el ? !el.classList.contains("hidden") : false
})

const networkFieldsVisible = extract((state) => {
  const el = state.document.getElementById("network-fields")
  return el ? !el.classList.contains("hidden") : false
})

const testBtnVisible = extract((state) => {
  const el = state.document.getElementById("cfg-test")
  return el ? !el.classList.contains("hidden") : false
})

const ephemeralChecked = extract((state) => {
  const el = state.document.getElementById("cfg-ephemeral") as HTMLInputElement | null
  return el?.checked ?? false
})

const ephemeralFieldsVisible = extract((state) => {
  const el = state.document.getElementById("ephemeral-fields")
  return el ? !el.classList.contains("hidden") : false
})

const cfgNameValue = extract((state) => {
  const el = state.document.getElementById("cfg-name") as HTMLInputElement | null
  return el?.value ?? ""
})

const cfgBaseUrlValue = extract((state) => {
  const el = state.document.getElementById("cfg-base-url") as HTMLInputElement | null
  return el?.value ?? ""
})

// --- properties ---

// password gate is always hidden (skipped in code)
export const passwordGateHidden = always(() => !passwordGateVisible.current)

// on start tab: exactly one of server-panel or config-page is visible
export const exclusivePanels = always(() => {
  if (activeTab.current !== "start") return true
  return serverPanelVisible.current !== configPageVisible.current
})

// running + stopped should equal total server count
export const statusCountsMatch = always(() => {
  if (activeTab.current !== "start") return true
  if (!serverPanelVisible.current) return true
  const total = serverCount.current
  if (total === 0) return true
  return (runningCount.current + stoppedCount.current) === total
})

// deployment "cloud" shows cloud fields, hides network fields
export const cloudFieldsMatchDeployment = always(() => {
  if (!configPageVisible.current) return true
  if (cfgDeployment.current === "cloud") {
    return cloudFieldsVisible.current && !networkFieldsVisible.current
  }
  return true
})

// deployment "network" shows network fields, hides cloud fields, shows test button
export const networkFieldsMatchDeployment = always(() => {
  if (!configPageVisible.current) return true
  if (cfgDeployment.current === "network") {
    return networkFieldsVisible.current && !cloudFieldsVisible.current && testBtnVisible.current
  }
  return true
})

// ephemeral checkbox controls ephemeral fields visibility
export const ephemeralFieldsSync = always(() => {
  if (!configPageVisible.current) return true
  if (!cloudFieldsVisible.current) return true
  return ephemeralChecked.current === ephemeralFieldsVisible.current
})

// clicking start on a stopped service should eventually show it as running
export const startServiceWorks = always(
  now(() => {
    // detect that a start button was just clicked (checking lastAction is tricky,
    // so we check: a button shows "Starting..." text)
    const btns = Array.from(
      (typeof document !== "undefined" ? document : null)?.querySelectorAll?.(".btn-start") ?? []
    )
    return btns.some((b) => b.textContent === "Starting...")
  }).implies(
    eventually(() => runningCount.current > 0).within(10, "seconds")
  )
)

// --- actions ---

// navigate to start tab
const startTabPoint = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="start"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const goToStartTab = actions(() => {
  const p = startTabPoint.current
  return p ? [{ Click: { name: "tab-start", point: p } }] : []
})

// open config page
const configBtnPoint = extract((state) => {
  const btn = state.document.getElementById("config-btn") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const openConfigPage = actions(() => {
  const p = configBtnPoint.current
  return p ? [{ Click: { name: "config-btn", point: p } }] : []
})

// back from config
const backBtnPoint = extract((state) => {
  const btn = state.document.getElementById("cfg-back") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const goBack = actions(() => {
  const p = backBtnPoint.current
  return p ? [{ Click: { name: "cfg-back", point: p } }] : []
})

// toggle deployment dropdown
const deploySelectPoint = extract((state) => {
  const sel = state.document.getElementById("cfg-deployment") as HTMLElement | null
  if (!sel || sel.offsetParent === null) return null
  const r = sel.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const toggleDeployment = actions(() => {
  const p = deploySelectPoint.current
  if (!p) return []
  return [{ Click: { name: "cfg-deployment", point: p } }]
})

// toggle ephemeral checkbox
const ephemeralPoint = extract((state) => {
  const cb = state.document.getElementById("cfg-ephemeral") as HTMLElement | null
  if (!cb || cb.offsetParent === null) return null
  const r = cb.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const toggleEphemeral = actions(() => {
  const p = ephemeralPoint.current
  return p ? [{ Click: { name: "cfg-ephemeral", point: p } }] : []
})

// fill config form name field
const cfgNamePoint = extract((state) => {
  const el = state.document.getElementById("cfg-name") as HTMLElement | null
  if (!el || el.offsetParent === null) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const nameGen = from(["test-svc", "my-api", "ollama-local", "cloud-1"])

export const fillName = actions(() => {
  const p = cfgNamePoint.current
  if (!p) return []
  return [
    { Click: { name: "cfg-name", point: p } },
    { TypeText: { text: nameGen.generate(), delayMillis: 30 } },
  ]
})

// fill base URL
const cfgBaseUrlPoint = extract((state) => {
  const el = state.document.getElementById("cfg-base-url") as HTMLElement | null
  if (!el || el.offsetParent === null) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const urlGen = from([
  "http://localhost:11434/v1",
  "https://api.openai.com/v1",
  "http://192.168.1.50:8080/v1",
])

export const fillBaseUrl = actions(() => {
  const p = cfgBaseUrlPoint.current
  if (!p) return []
  return [
    { Click: { name: "cfg-base-url", point: p } },
    { TypeText: { text: urlGen.generate(), delayMillis: 30 } },
  ]
})

// click save button
const saveBtnPoint = extract((state) => {
  const btn = state.document.getElementById("cfg-save") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const clickSave = actions(() => {
  const p = saveBtnPoint.current
  return p ? [{ Click: { name: "cfg-save", point: p } }] : []
})

// click start/stop buttons on servers
const serverButtons = extract((state) => {
  const btns = state.document.querySelectorAll(".btn-start, .btn-stop")
  const result: { name: string; point: { x: number; y: number } }[] = []
  btns.forEach((b) => {
    const el = b as HTMLElement
    if (el.offsetParent === null) return
    const r = el.getBoundingClientRect()
    result.push({
      name: el.classList.contains("btn-start") ? "start-svc" : "stop-svc",
      point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
    })
  })
  return result
})

export const clickServerButtons = actions(() => {
  return serverButtons.current.map((b) => ({
    Click: { name: b.name, point: b.point },
  }) as Action)
})
