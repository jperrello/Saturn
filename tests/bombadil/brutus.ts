import {
  extract, always, now, eventually,
  actions, weighted, from,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// test the Brutus tab — warning gate, chat, tunnel controls, backends

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// --- extractors ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

const gateVisible = extract((state) => {
  const gate = state.document.getElementById("brutus-gate")
  return gate ? !gate.classList.contains("hidden") : false
})

const mainVisible = extract((state) => {
  const main = state.document.getElementById("brutus-main")
  return main ? !main.classList.contains("hidden") : false
})

const acceptBtnPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-accept") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const brutusWelcomeVisible = extract((state) => {
  const w = state.document.getElementById("brutus-welcome")
  return w ? !w.classList.contains("hidden") : false
})

const brutusMessageCount = extract((state) =>
  state.document.querySelectorAll("#brutus-messages .msg").length
)

const brutusUserCount = extract((state) =>
  state.document.querySelectorAll("#brutus-messages .msg.user").length
)

const brutusAssistantCount = extract((state) =>
  state.document.querySelectorAll("#brutus-messages .msg.assistant").length
)

const brutusSendDisabled = extract((state) => {
  const btn = state.document.getElementById("brutus-send") as HTMLButtonElement | null
  return btn?.disabled ?? false
})

const brutusStatusText = extract((state) => {
  const el = state.document.getElementById("brutus-status")
  return el?.textContent?.trim() ?? ""
})

const brutusInput = extract((state) => {
  const el = state.document.getElementById("brutus-input") as HTMLInputElement | null
  if (!el) return null
  const r = el.getBoundingClientRect()
  return {
    value: el.value,
    point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
  }
})

const tunnelStatusText = extract((state) => {
  const el = state.document.getElementById("brutus-tunnel-status")
  return el?.textContent?.trim() ?? ""
})

const tunnelStartVisible = extract((state) => {
  const btn = state.document.getElementById("brutus-tunnel-start")
  return btn ? !btn.classList.contains("hidden") : false
})

const tunnelStopVisible = extract((state) => {
  const btn = state.document.getElementById("brutus-tunnel-stop")
  return btn ? !btn.classList.contains("hidden") : false
})

const backendCount = extract((state) =>
  state.document.querySelectorAll("#brutus-backends .brutus-backend-item").length
)

const exampleButtons = extract((state) => {
  const btns = state.document.querySelectorAll(".brutus-example")
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

const clearBtnPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-clear") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const accepted = extract((state) => {
  try {
    return state.window.localStorage.getItem("brutus-accepted") === "1"
  } catch {
    return false
  }
})

// --- properties ---

// gate and main are mutually exclusive on the brutus tab
export const gateMainExclusive = always(() => {
  if (activeTab.current !== "brutus") return true
  return gateVisible.current !== mainVisible.current
})

// if user previously accepted, gate should be hidden
export const acceptedSkipsGate = always(() => {
  if (activeTab.current !== "brutus") return true
  if (!accepted.current) return true
  return !gateVisible.current && mainVisible.current
})

// welcome visible when no messages
export const welcomeWhenEmpty = always(() => {
  if (activeTab.current !== "brutus") return true
  if (!mainVisible.current) return true
  if (brutusMessageCount.current === 0) return brutusWelcomeVisible.current
  return true
})

// welcome hidden when messages exist
export const welcomeHiddenWhenMessages = always(() => {
  if (activeTab.current !== "brutus") return true
  if (!mainVisible.current) return true
  if (brutusMessageCount.current > 0) return !brutusWelcomeVisible.current
  return true
})

// user/assistant messages alternate correctly
export const messageOrdering = always(() => {
  if (activeTab.current !== "brutus") return true
  const u = brutusUserCount.current
  const a = brutusAssistantCount.current
  return u >= a && (u - a) <= 1
})

// send button should recover from disabled state
export const sendBtnRecovers = always(
  now(() => brutusSendDisabled.current).implies(
    eventually(() => !brutusSendDisabled.current).within(30, "seconds")
  )
)

// status should return to idle after streaming
export const statusReturnsIdle = always(
  now(() => brutusStatusText.current === "● streaming").implies(
    eventually(() => brutusStatusText.current === "● idle").within(30, "seconds")
  )
)

// tunnel start and stop buttons are mutually exclusive
export const tunnelButtonsExclusive = always(() => {
  if (activeTab.current !== "brutus") return true
  if (!mainVisible.current) return true
  return tunnelStartVisible.current !== tunnelStopVisible.current
})

// 3 example buttons visible when welcome screen is shown
export const threeExamples = always(() => {
  if (activeTab.current !== "brutus") return true
  if (!mainVisible.current) return true
  if (!brutusWelcomeVisible.current) return true
  return exampleButtons.current.length === 3
})

// --- actions ---

// navigate to brutus tab
const brutusTabPoint = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="brutus"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const goToBrutusTab = actions(() => {
  const p = brutusTabPoint.current
  return p ? [{ Click: { name: "tab-brutus", point: p } }] : []
})

// accept the warning gate
export const acceptGate = actions(() => {
  const p = acceptBtnPoint.current
  return p ? [{ Click: { name: "brutus-accept", point: p } }] : []
})

// click example prompts
export const clickExamples = actions(() =>
  exampleButtons.current.map((ex) => ({
    Click: { name: `brutus-example-${ex.text}`, point: ex.point },
  }) as Action)
)

// type and send a message
const brutusMessages = from(["Hello", "What can you do?", "test", "Tell me a joke"])

export const typeAndSend = actions(() => {
  const inp = brutusInput.current
  if (!inp) return []
  return [
    { Click: { name: "brutus-input", point: inp.point } },
    { TypeText: { text: brutusMessages.generate(), delayMillis: 30 } },
    { PressKey: { code: 13 } },
  ]
})

// click send button
const sendBtnPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-send") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const clickSend = actions(() => {
  const p = sendBtnPoint.current
  if (!p || brutusSendDisabled.current) return []
  return [{ Click: { name: "brutus-send", point: p } }]
})

// click clear button
export const clickClear = actions(() => {
  const p = clearBtnPoint.current
  return p ? [{ Click: { name: "brutus-clear", point: p } }] : []
})

// tunnel controls
const tunnelStartPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-tunnel-start") as HTMLElement | null
  if (!btn || btn.classList.contains("hidden")) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const tunnelStopPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-tunnel-stop") as HTMLElement | null
  if (!btn || btn.classList.contains("hidden")) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const lanOnlyPoint = extract((state) => {
  const btn = state.document.getElementById("brutus-qr-refresh") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const clickTunnelControls = actions(() => {
  const result: Action[] = []
  const start = tunnelStartPoint.current
  const stop = tunnelStopPoint.current
  const lan = lanOnlyPoint.current
  if (start) result.push({ Click: { name: "tunnel-start", point: start } })
  if (stop) result.push({ Click: { name: "tunnel-stop", point: stop } })
  if (lan) result.push({ Click: { name: "lan-only", point: lan } })
  return result
})

// tab navigation weighted toward brutus
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
    const p = brutusTabPoint.current
    return p ? [{ Click: { name: "tab-brutus", point: p } }] : []
  })],
  [1, actions(() => {
    return tabPoints.current
      .filter((t) => t.name !== "brutus")
      .map((t) => ({ Click: { name: `tab-${t.name}`, point: t.point } }) as Action)
  })],
])
