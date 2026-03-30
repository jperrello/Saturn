import {
  extract, always, now, next, eventually,
  actions, weighted, from,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// full Saturn web UI test suite — all tabs, all states

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// ═══════════════════════════════════════════
//  EXTRACTORS
// ═══════════════════════════════════════════

// --- global ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

const activePage = extract((state) => {
  const page = state.document.querySelector(".page.active") as HTMLElement | null
  return page?.id ?? null
})

const tabCount = extract((state) =>
  state.document.querySelectorAll(".tab").length
)

const hasOverflow = extract((state) => {
  const app = state.document.querySelector(".app") as HTMLElement | null
  if (!app) return false
  return app.scrollWidth > state.window.innerWidth + 10
})

// --- discover tab ---

const discoverBtn = extract((state) => {
  const btn = state.document.getElementById("discover-btn") as HTMLButtonElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return {
    disabled: btn.disabled,
    text: btn.textContent?.trim() ?? "",
    point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
  }
})

const serviceListCount = extract((state) =>
  state.document.querySelectorAll("#services-list .checklist-item").length
)

const onlineCount = extract((state) =>
  state.document.querySelectorAll("#services-list .status-online").length
)

const offlineCount = extract((state) =>
  state.document.querySelectorAll("#services-list .status-offline").length
)

const moonCount = extract((state) => {
  const w = state.window as any
  return w.saturnMoons?.length ?? 0
})

const selectedMoonCount = extract((state) => {
  const w = state.window as any
  return (w.saturnMoons ?? []).filter((m: any) => m.selected).length
})

const serviceItems = extract((state) => {
  const items = state.document.querySelectorAll("#services-list .checklist-item")
  const result: { checked: boolean }[] = []
  items.forEach((item) => {
    const cb = item.querySelector('input[type="checkbox"]') as HTMLInputElement | null
    result.push({ checked: cb?.checked ?? false })
  })
  return result
})

const discovering = extract((state) => {
  const left = state.document.querySelector(".discover-left")
  return left?.classList?.contains("discovering") ?? false
})

// --- start tab ---

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
  const first = items[0]?.textContent?.trim() ?? ""
  if (first.includes("No services configured")) return 0
  return items.length
})

const runningBadgeCount = extract((state) =>
  state.document.querySelectorAll(".status-up").length
)

const stoppedBadgeCount = extract((state) =>
  state.document.querySelectorAll(".status-down").length
)

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

// --- chat tab ---

const welcomeVisible = extract((state) => {
  const w = state.document.getElementById("welcome")
  return w ? !w.classList.contains("hidden") : false
})

const messageCount = extract((state) =>
  state.document.querySelectorAll(".msg").length
)

const userMsgCount = extract((state) =>
  state.document.querySelectorAll(".msg.user").length
)

const assistantMsgCount = extract((state) =>
  state.document.querySelectorAll(".msg.assistant").length
)

const sendBtnDisabled = extract((state) => {
  const btn = state.document.getElementById("send-btn") as HTMLButtonElement | null
  return btn?.disabled ?? false
})

const hasStreamingCursor = extract((state) =>
  state.document.querySelector(".cursor") !== null
)

const exampleBtns = extract((state) => {
  const btns = state.document.querySelectorAll(".example")
  const result: { text: string; point: { x: number; y: number } }[] = []
  btns.forEach((b) => {
    const el = b as HTMLElement
    if (el.offsetParent === null) return
    const r = el.getBoundingClientRect()
    if (r.width === 0) return
    result.push({
      text: el.textContent?.trim() ?? "",
      point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
    })
  })
  return result
})

const serviceSelectInfo = extract((state) => {
  const sel = state.document.getElementById("service-select") as HTMLSelectElement | null
  if (!sel) return null
  const r = sel.getBoundingClientRect()
  return {
    value: sel.value,
    text: sel.options[sel.selectedIndex]?.text ?? "",
    point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
  }
})

const modelSelectInfo = extract((state) => {
  const sel = state.document.getElementById("model-select") as HTMLSelectElement | null
  if (!sel) return null
  const r = sel.getBoundingClientRect()
  return {
    value: sel.value,
    point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
  }
})

// ═══════════════════════════════════════════
//  PROPERTIES — GLOBAL
// ═══════════════════════════════════════════

export const threeTabsExist = always(() => tabCount.current === 3)

export const tabMatchesPage = always(() => activeTab.current === activePage.current)

export const oneTabActive = always(() => activeTab.current !== null)

export const noHorizontalOverflow = always(() => !hasOverflow.current)

// ═══════════════════════════════════════════
//  PROPERTIES — DISCOVER
// ═══════════════════════════════════════════

export const discoverBtnValidText = always(() => {
  const btn = discoverBtn.current
  if (!btn) return true
  return btn.text === "Discover" || btn.text === "Scanning..."
})

export const discoverBtnDisabledSync = always(() => {
  const btn = discoverBtn.current
  if (!btn) return true
  if (btn.text === "Scanning...") return btn.disabled
  return !btn.disabled
})

export const servicesHaveStatus = always(() => {
  if (serviceListCount.current === 0) return true
  return (onlineCount.current + offlineCount.current) === serviceListCount.current
})

export const moonCountMatchesOnline = always(() => {
  if (activeTab.current !== "discover") return true
  return moonCount.current === onlineCount.current
})

export const checkboxMoonSync = always(() => {
  if (activeTab.current !== "discover") return true
  const checked = serviceItems.current.filter((i) => i.checked).length
  return checked === selectedMoonCount.current
})

export const discoverBtnRecovers = always(
  now(() => discoverBtn.current?.disabled === true).implies(
    eventually(() => discoverBtn.current?.disabled === false).within(12, "seconds")
  )
)

export const discoveringTransient = always(
  now(() => discovering.current).implies(
    eventually(() => !discovering.current).within(12, "seconds")
  )
)

// ═══════════════════════════════════════════
//  PROPERTIES — START
// ═══════════════════════════════════════════

export const passwordGateHidden = always(() => !passwordGateVisible.current)

export const exclusivePanels = always(() => {
  if (activeTab.current !== "start") return true
  return serverPanelVisible.current !== configPageVisible.current
})

export const statusCountsMatch = always(() => {
  if (activeTab.current !== "start") return true
  if (!serverPanelVisible.current) return true
  const total = serverCount.current
  if (total === 0) return true
  return (runningBadgeCount.current + stoppedBadgeCount.current) === total
})

export const cloudFieldsMatchDeployment = always(() => {
  if (!configPageVisible.current) return true
  if (cfgDeployment.current === "cloud") {
    return cloudFieldsVisible.current && !networkFieldsVisible.current
  }
  return true
})

export const networkFieldsMatchDeployment = always(() => {
  if (!configPageVisible.current) return true
  if (cfgDeployment.current === "network") {
    return networkFieldsVisible.current && !cloudFieldsVisible.current && testBtnVisible.current
  }
  return true
})

export const ephemeralFieldsSync = always(() => {
  if (!configPageVisible.current) return true
  if (!cloudFieldsVisible.current) return true
  return ephemeralChecked.current === ephemeralFieldsVisible.current
})

// ═══════════════════════════════════════════
//  PROPERTIES — CHAT
// ═══════════════════════════════════════════

export const welcomeWhenEmpty = always(() => {
  if (activeTab.current !== "chat") return true
  if (messageCount.current === 0) return welcomeVisible.current
  return true
})

export const welcomeHiddenWhenMessages = always(() => {
  if (activeTab.current !== "chat") return true
  if (messageCount.current > 0) return !welcomeVisible.current
  return true
})

export const messageOrdering = always(() => {
  if (activeTab.current !== "chat") return true
  const u = userMsgCount.current
  const a = assistantMsgCount.current
  return u >= a && (u - a) <= 1
})

export const sendBtnRecovers = always(
  now(() => sendBtnDisabled.current).implies(
    eventually(() => !sendBtnDisabled.current).within(30, "seconds")
  )
)

export const cursorDisappears = always(
  now(() => hasStreamingCursor.current).implies(
    eventually(() => !hasStreamingCursor.current).within(30, "seconds")
  )
)

export const threeExamples = always(() => {
  if (activeTab.current !== "chat") return true
  if (!welcomeVisible.current) return true
  return exampleBtns.current.length === 3
})

// --- toast (replaces alert) ---

const toastVisible = extract((state) => {
  const el = state.document.getElementById("toast")
  return el ? !el.classList.contains("hidden") : false
})

// toasts should auto-dismiss within 5 seconds
export const toastDismisses = always(
  now(() => toastVisible.current).implies(
    eventually(() => !toastVisible.current).within(5, "seconds")
  )
)

// ═══════════════════════════════════════════
//  ACTIONS
// ═══════════════════════════════════════════

// --- helper: get clickable point for an element ---

function point(state: any, selector: string) {
  const el = state.document.querySelector(selector) as HTMLElement | null
  if (!el || el.offsetParent === null) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0) return null
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
}

// --- tab navigation ---

const tabPoints = extract((state) => {
  const tabs = state.document.querySelectorAll(".tab")
  const result: { name: string; point: { x: number; y: number } }[] = []
  tabs.forEach((t) => {
    const el = t as HTMLElement
    const r = el.getBoundingClientRect()
    result.push({
      name: el.dataset.tab ?? "unknown",
      point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
    })
  })
  return result
})

export const clickTabs = actions(() =>
  tabPoints.current.map((t) => ({
    Click: { name: `tab-${t.name}`, point: t.point },
  }) as Action)
)

// --- discover ---

export const clickDiscover = actions(() => {
  const btn = discoverBtn.current
  if (!btn || btn.disabled) return []
  return [{ Click: { name: "discover-btn", point: btn.point } }]
})

const checkboxPoints = extract((state) => {
  const items = state.document.querySelectorAll("#services-list .checklist-item")
  const result: { name: string; point: { x: number; y: number } }[] = []
  items.forEach((item) => {
    const cb = item.querySelector('input[type="checkbox"]') as HTMLElement | null
    if (!cb) return
    const name = item.querySelector(".name")?.textContent?.trim() ?? "svc"
    const r = cb.getBoundingClientRect()
    if (r.width === 0) return
    result.push({ name, point: { x: r.left + r.width / 2, y: r.top + r.height / 2 } })
  })
  return result
})

export const toggleCheckboxes = actions(() =>
  checkboxPoints.current.map((cb) => ({
    Click: { name: `checkbox-${cb.name}`, point: cb.point },
  }) as Action)
)

// --- start tab ---

const configBtnPoint = extract((state) => {
  const btn = state.document.getElementById("config-btn") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const backBtnPoint = extract((state) => {
  const btn = state.document.getElementById("cfg-back") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const configNavigation = actions(() => {
  const result: Action[] = []
  const cfg = configBtnPoint.current
  const back = backBtnPoint.current
  if (cfg) result.push({ Click: { name: "config-btn", point: cfg } })
  if (back) result.push({ Click: { name: "cfg-back", point: back } })
  return result
})

const deploySelectPoint = extract((state) => {
  const sel = state.document.getElementById("cfg-deployment") as HTMLElement | null
  if (!sel || sel.offsetParent === null) return null
  const r = sel.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const toggleDeployment = actions(() => {
  const p = deploySelectPoint.current
  return p ? [{ Click: { name: "cfg-deployment", point: p } }] : []
})

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

export const clickServerButtons = actions(() =>
  serverButtons.current.map((b) => ({
    Click: { name: b.name, point: b.point },
  }) as Action)
)

const cfgNamePoint = extract((state) => {
  const el = state.document.getElementById("cfg-name") as HTMLElement | null
  if (!el || el.offsetParent === null) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const cfgBaseUrlPoint = extract((state) => {
  const el = state.document.getElementById("cfg-base-url") as HTMLElement | null
  if (!el || el.offsetParent === null) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const saveBtnPoint = extract((state) => {
  const btn = state.document.getElementById("cfg-save") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const nameGen = from(["test-svc", "my-api", "ollama-local", "cloud-1"])
const urlGen = from([
  "http://localhost:11434/v1",
  "https://api.openai.com/v1",
  "http://192.168.1.50:8080/v1",
])

export const fillAndSaveConfig = actions(() => {
  const name = cfgNamePoint.current
  const url = cfgBaseUrlPoint.current
  const save = saveBtnPoint.current
  if (!name || !url || !save) return []
  return [
    { Click: { name: "cfg-name", point: name } },
    { TypeText: { text: nameGen.generate(), delayMillis: 30 } },
    { Click: { name: "cfg-base-url", point: url } },
    { TypeText: { text: urlGen.generate(), delayMillis: 30 } },
    { Click: { name: "cfg-save", point: save } },
  ]
})

// --- chat ---

const chatInputPoint = extract((state) => {
  const el = state.document.getElementById("chat-input") as HTMLInputElement | null
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const newChatBtnPoint = extract((state) => {
  const btn = state.document.getElementById("new-chat-btn") as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const historyItemPoints = extract((state) => {
  const items = state.document.querySelectorAll("#history-list .history-item")
  const result: { idx: number; point: { x: number; y: number } }[] = []
  items.forEach((item, i) => {
    const el = item as HTMLElement
    const r = el.getBoundingClientRect()
    if (r.width === 0) return
    result.push({ idx: i, point: { x: r.left + r.width / 2, y: r.top + r.height / 2 } })
  })
  return result
})

export const clickExamples = actions(() =>
  exampleBtns.current.map((ex) => ({
    Click: { name: `example-${ex.text}`, point: ex.point },
  }) as Action)
)

const chatMessages = from(["Hello", "What is Saturn?", "Help me debug this", "test"])

export const typeAndSend = actions(() => {
  const inp = chatInputPoint.current
  if (!inp) return []
  return [
    { Click: { name: "chat-input", point: inp } },
    { TypeText: { text: chatMessages.generate(), delayMillis: 30 } },
    { PressKey: { code: 13 } },
  ]
})

export const clickNewChat = actions(() => {
  const p = newChatBtnPoint.current
  return p ? [{ Click: { name: "new-chat-btn", point: p } }] : []
})

export const clickHistory = actions(() =>
  historyItemPoints.current.map((h) => ({
    Click: { name: `history-${h.idx}`, point: h.point },
  }) as Action)
)

export const clickServiceSelect = actions(() => {
  const s = serviceSelectInfo.current
  return s ? [{ Click: { name: "service-select", point: s.point } }] : []
})

export const clickModelSelect = actions(() => {
  const m = modelSelectInfo.current
  return m ? [{ Click: { name: "model-select", point: m.point } }] : []
})
