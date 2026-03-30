import {
  extract, always, now, next, eventually,
  actions, weighted,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// test the Discover tab — mDNS scan, service list, checkbox-moon sync
// run AFTER services are configured/started via the Start tab

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// --- extractors ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

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

const serviceItems = extract((state) => {
  const items = state.document.querySelectorAll("#services-list .checklist-item")
  const result: { name: string; status: string; checked: boolean }[] = []
  items.forEach((item) => {
    const name = item.querySelector(".name")?.textContent?.trim() ?? ""
    const status = item.querySelector(".status")?.textContent?.trim() ?? ""
    const cb = item.querySelector('input[type="checkbox"]') as HTMLInputElement | null
    result.push({ name, status, checked: cb?.checked ?? false })
  })
  return result
})

const serviceCount = extract((state) =>
  state.document.querySelectorAll("#services-list .checklist-item").length
)

const onlineCount = extract((state) =>
  state.document.querySelectorAll("#services-list .status-online").length
)

const offlineCount = extract((state) =>
  state.document.querySelectorAll("#services-list .status-offline").length
)

const moonCount = extract((state) => {
  // moons are tracked in window.saturnMoons
  const w = state.window as any
  return w.saturnMoons?.length ?? 0
})

const selectedMoonCount = extract((state) => {
  const w = state.window as any
  const moons = w.saturnMoons ?? []
  return moons.filter((m: any) => m.selected).length
})

const discovering = extract((state) => {
  const left = state.document.querySelector(".discover-left")
  return left?.classList?.contains("discovering") ?? false
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

// --- properties ---

// discover button exists and is visible on discover tab
export const discoverBtnExists = always(() => {
  if (activeTab.current !== "discover") return true
  return discoverBtn.current !== null
})

// button text is either "Discover" or "Scanning..."
export const discoverBtnValidText = always(() => {
  const btn = discoverBtn.current
  if (!btn) return true
  return btn.text === "Discover" || btn.text === "Scanning..."
})

// button is disabled iff text is "Scanning..."
export const discoverBtnDisabledSync = always(() => {
  const btn = discoverBtn.current
  if (!btn) return true
  if (btn.text === "Scanning...") return btn.disabled
  return !btn.disabled
})

// after discovery, every service has a status badge (online or offline)
export const servicesHaveStatus = always(() => {
  if (serviceCount.current === 0) return true
  return (onlineCount.current + offlineCount.current) === serviceCount.current
})

// moon count matches online service count
export const moonCountMatchesOnline = always(() => {
  if (activeTab.current !== "discover") return true
  // moons only created from online services
  return moonCount.current === onlineCount.current
})

// checking a checkbox makes the corresponding moon selected
export const checkboxMoonSync = always(() => {
  if (activeTab.current !== "discover") return true
  const items = serviceItems.current
  const checked = items.filter((i) => i.checked).length
  return checked === selectedMoonCount.current
})

// discover button recovers from scanning state
export const discoverBtnRecovers = always(
  now(() => discoverBtn.current?.disabled === true).implies(
    eventually(() => discoverBtn.current?.disabled === false).within(12, "seconds")
  )
)

// discovering state is transient
export const discoveringTransient = always(
  now(() => discovering.current).implies(
    eventually(() => !discovering.current).within(12, "seconds")
  )
)

// after clicking discover, services should eventually appear (if any are running)
export const servicesAppearAfterScan = always(
  now(() => discoverBtn.current?.text === "Scanning...").implies(
    eventually(() => serviceCount.current > 0 || discoverBtn.current?.text === "Discover")
      .within(12, "seconds")
  )
)

// --- actions ---

// navigate to discover tab
const discoverTabPoint = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="discover"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const goToDiscoverTab = actions(() => {
  const p = discoverTabPoint.current
  return p ? [{ Click: { name: "tab-discover", point: p } }] : []
})

// click discover button
export const clickDiscover = actions(() => {
  const btn = discoverBtn.current
  if (!btn || btn.disabled) return []
  return [{ Click: { name: "discover-btn", point: btn.point } }]
})

// toggle service checkboxes
export const toggleCheckboxes = actions(() => {
  return checkboxPoints.current.map((cb) => ({
    Click: { name: `checkbox-${cb.name}`, point: cb.point },
  }) as Action)
})

// all tabs for general navigation
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

export const clickTabs = weighted([
  [5, actions(() => {
    const p = discoverTabPoint.current
    return p ? [{ Click: { name: "tab-discover", point: p } }] : []
  })],
  [1, actions(() => {
    return tabPoints.current
      .filter((t) => t.name !== "discover")
      .map((t) => ({ Click: { name: `tab-${t.name}`, point: t.point } }) as Action)
  })],
])
