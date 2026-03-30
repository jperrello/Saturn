import {
  extract, always, now, eventually,
  actions, weighted,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// test the UI with zero services configured — the "cold start" experience

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// --- extractors ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

// discover tab
const discoverBtn = extract((state) => {
  const btn = state.document.getElementById("discover-btn") as HTMLButtonElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { disabled: btn.disabled, text: btn.textContent?.trim() ?? "", point: { x: r.left + r.width / 2, y: r.top + r.height / 2 } }
})

const serviceListCount = extract((state) =>
  state.document.querySelectorAll("#services-list .checklist-item").length
)

// start tab
const serverListEmpty = extract((state) => {
  const list = state.document.getElementById("server-list")
  if (!list) return true
  const items = list.querySelectorAll(".checklist-item")
  if (items.length === 0) return true
  // check if it's the "No services configured" placeholder
  const first = items[0]?.textContent?.trim() ?? ""
  return first.includes("No services configured")
})

const serverPanelVisible = extract((state) => {
  const panel = state.document.getElementById("server-panel")
  return panel ? !panel.classList.contains("hidden") : false
})

const configPageVisible = extract((state) => {
  const page = state.document.getElementById("config-page")
  return page ? !page.classList.contains("hidden") : false
})

// chat tab
const chatServiceSelect = extract((state) => {
  const sel = state.document.getElementById("service-select") as HTMLSelectElement | null
  if (!sel) return null
  return { value: sel.value, text: sel.options[sel.selectedIndex]?.text ?? "" }
})

const chatWelcomeVisible = extract((state) => {
  const w = state.document.getElementById("welcome")
  return w ? !w.classList.contains("hidden") : false
})

// --- properties ---

// discover tab starts empty (no services found before scanning)
export const emptyDiscoverList = always(() => {
  if (activeTab.current !== "discover") return true
  return serviceListCount.current === 0 || discoverBtn.current?.text === "Scanning..."
})

// start tab shows empty server list when no services configured
export const emptyServerList = always(() => {
  if (activeTab.current !== "start") return true
  if (!serverPanelVisible.current) return true
  return serverListEmpty.current
})

// chat shows "discover first" when no services discovered
export const chatNeedsDiscovery = always(() => {
  if (activeTab.current !== "chat") return true
  const sel = chatServiceSelect.current
  if (!sel) return true
  return sel.text.includes("discover first") || sel.value === ""
})

// chat welcome screen visible when no messages sent
export const chatWelcomeShown = always(() => {
  if (activeTab.current !== "chat") return true
  return chatWelcomeVisible.current
})

// discover button is never stuck disabled (should re-enable after scan)
export const discoverBtnRecovers = always(
  now(() => discoverBtn.current?.disabled === true).implies(
    eventually(() => discoverBtn.current?.disabled === false).within(10, "seconds")
  )
)

// --- actions ---

// click tabs
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

export const clickTabs = actions(() => {
  return tabPoints.current.map((t) => ({
    Click: { name: `tab-${t.name}`, point: t.point },
  }) as Action)
})

// click discover button
export const clickDiscover = actions(() => {
  const btn = discoverBtn.current
  if (!btn || btn.disabled) return []
  return [{ Click: { name: "discover-btn", point: btn.point } }]
})

// click "Configure New Service" to explore config page in empty state
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

export const exploreConfigPage = actions(() => {
  const result: Action[] = []
  const cfg = configBtnPoint.current
  const back = backBtnPoint.current
  if (cfg) result.push({ Click: { name: "config-btn", point: cfg } })
  if (back) result.push({ Click: { name: "cfg-back", point: back } })
  return result
})
