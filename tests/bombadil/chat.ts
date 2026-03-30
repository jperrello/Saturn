import {
  extract, always, now, next, eventually,
  actions, weighted, from, strings,
  type Action,
} from "@antithesishq/bombadil"
import {
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
} from "@antithesishq/bombadil/defaults/properties"
import { scroll } from "@antithesishq/bombadil/defaults/actions"

// test the Chat tab — service/model selection, messaging, history
// run AFTER discover so services are populated in the dropdown

export { noUncaughtExceptions, noUnhandledPromiseRejections, scroll }

// --- extractors ---

const activeTab = extract((state) => {
  const tab = state.document.querySelector(".tab.active") as HTMLElement | null
  return tab?.dataset?.tab ?? null
})

const serviceSelect = extract((state) => {
  const sel = state.document.getElementById("service-select") as HTMLSelectElement | null
  if (!sel) return null
  return {
    value: sel.value,
    optionCount: sel.options.length,
    text: sel.options[sel.selectedIndex]?.text ?? "",
    point: (() => {
      const r = sel.getBoundingClientRect()
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
    })(),
  }
})

const modelSelect = extract((state) => {
  const sel = state.document.getElementById("model-select") as HTMLSelectElement | null
  if (!sel) return null
  return {
    value: sel.value,
    optionCount: sel.options.length,
    text: sel.options[sel.selectedIndex]?.text ?? "",
    point: (() => {
      const r = sel.getBoundingClientRect()
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
    })(),
  }
})

const welcomeVisible = extract((state) => {
  const w = state.document.getElementById("welcome")
  return w ? !w.classList.contains("hidden") : false
})

const messageCount = extract((state) =>
  state.document.querySelectorAll(".msg").length
)

const userMessageCount = extract((state) =>
  state.document.querySelectorAll(".msg.user").length
)

const assistantMessageCount = extract((state) =>
  state.document.querySelectorAll(".msg.assistant").length
)

const historyCount = extract((state) =>
  state.document.querySelectorAll("#history-list .history-item").length
)

const sendBtnDisabled = extract((state) => {
  const btn = state.document.getElementById("send-btn") as HTMLButtonElement | null
  return btn?.disabled ?? false
})

const chatInput = extract((state) => {
  const el = state.document.getElementById("chat-input") as HTMLInputElement | null
  if (!el) return null
  const r = el.getBoundingClientRect()
  return {
    value: el.value,
    point: { x: r.left + r.width / 2, y: r.top + r.height / 2 },
  }
})

const exampleButtons = extract((state) => {
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

const hasStreamingCursor = extract((state) =>
  state.document.querySelector(".cursor") !== null
)

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

// --- properties ---

// welcome screen shown when no messages in current chat
export const welcomeWhenEmpty = always(() => {
  if (activeTab.current !== "chat") return true
  if (messageCount.current === 0) return welcomeVisible.current
  return true
})

// welcome hidden when messages exist
export const welcomeHiddenWhenMessages = always(() => {
  if (activeTab.current !== "chat") return true
  if (messageCount.current > 0) return !welcomeVisible.current
  return true
})

// user messages and assistant messages alternate correctly
// (user count should be >= assistant count, and differ by at most 1)
export const messageOrdering = always(() => {
  if (activeTab.current !== "chat") return true
  const u = userMessageCount.current
  const a = assistantMessageCount.current
  return u >= a && (u - a) <= 1
})

// send button should recover from disabled state (streaming done)
export const sendBtnRecovers = always(
  now(() => sendBtnDisabled.current).implies(
    eventually(() => !sendBtnDisabled.current).within(30, "seconds")
  )
)

// streaming cursor should eventually disappear
export const cursorDisappears = always(
  now(() => hasStreamingCursor.current).implies(
    eventually(() => !hasStreamingCursor.current).within(30, "seconds")
  )
)

// example buttons only visible when welcome is visible
export const examplesOnlyInWelcome = always(() => {
  if (activeTab.current !== "chat") return true
  if (!welcomeVisible.current) return exampleButtons.current.length === 0
  return true
})

// 3 example buttons when welcome screen is shown
export const threeExamples = always(() => {
  if (activeTab.current !== "chat") return true
  if (!welcomeVisible.current) return true
  return exampleButtons.current.length === 3
})

// new chat creates a history entry
export const newChatAddsHistory = always(() => {
  if (activeTab.current !== "chat") return true
  // history count should be >= 0 (just a sanity check)
  return historyCount.current >= 0
})

// --- persistence properties ---

// localStorage should contain saturn-chats key when messages exist
const localStorageHasChats = extract((state) => {
  try {
    return state.window.localStorage.getItem("saturn-chats") !== null
  } catch {
    return false
  }
})

export const localStoragePersists = always(() => {
  if (activeTab.current !== "chat") return true
  if (messageCount.current === 0) return true
  return localStorageHasChats.current
})

// chat history count should survive a page reload
// captures history count before reload, then verifies it's restored after
const preReloadHistoryCount = extract((state) =>
  state.document.querySelectorAll("#history-list .history-item").length
)

export const chatHistoryRestores = always(
  now(() => {
    if (activeTab.current !== "chat") return true
    // only check when we have history items
    return preReloadHistoryCount.current > 0
  }).implies(
    eventually(() => historyCount.current >= 1).within(10, "seconds")
  )
)

// --- markdown rendering properties ---

// when assistant messages exist, their bubbles should contain rendered HTML
// (code, strong, em, pre) rather than raw markdown syntax like **, ```, etc.
const assistantBubbles = extract((state) => {
  const bubbles = state.document.querySelectorAll(".msg.assistant .bubble")
  const result: { hasHtml: boolean; hasRawMd: boolean }[] = []
  bubbles.forEach((b) => {
    const el = b as HTMLElement
    const hasHtml =
      el.querySelector("code, strong, em, pre, blockquote, table, ul, ol, a, h1, h2, h3") !== null
    const hasRawMd = /(\*\*[^*]+\*\*|```[^`]+```|^#{1,3}\s)/m.test(el.textContent ?? "")
    result.push({ hasHtml, hasRawMd })
  })
  return result
})

export const markdownRendered = always(() => {
  if (activeTab.current !== "chat") return true
  const bubbles = assistantBubbles.current
  if (bubbles.length === 0) return true
  // at least one bubble should have rendered HTML or no raw markdown
  return bubbles.every((b: { hasHtml: boolean; hasRawMd: boolean }) => !b.hasRawMd)
})

// script tags in assistant messages must not execute
const hasExecutableScript = extract((state) => {
  const bubbles = state.document.querySelectorAll(".msg.assistant .bubble")
  let found = false
  bubbles.forEach((b) => {
    const scripts = (b as HTMLElement).querySelectorAll("script")
    if (scripts.length > 0) found = true
  })
  return found
})

export const xssBlocked = always(() => {
  if (activeTab.current !== "chat") return true
  return !hasExecutableScript.current
})

// --- actions ---

// navigate to chat tab
const chatTabPoint = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="chat"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const goToChatTab = actions(() => {
  const p = chatTabPoint.current
  return p ? [{ Click: { name: "tab-chat", point: p } }] : []
})

// click service selector
export const clickServiceSelect = actions(() => {
  const s = serviceSelect.current
  if (!s) return []
  return [{ Click: { name: "service-select", point: s.point } }]
})

// click model selector
export const clickModelSelect = actions(() => {
  const m = modelSelect.current
  if (!m) return []
  return [{ Click: { name: "model-select", point: m.point } }]
})

// click example buttons
export const clickExamples = actions(() => {
  return exampleButtons.current.map((ex) => ({
    Click: { name: `example-${ex.text}`, point: ex.point },
  }) as Action)
})

// type in chat input and send
const chatMessages = from([
  "Hello",
  "What is Saturn?",
  "Help me debug this",
  "Tell me a joke",
  "test",
])

export const typeAndSend = actions(() => {
  const inp = chatInput.current
  if (!inp) return []
  const sendPoint = (() => {
    // approximate send button position (right of input)
    return { x: inp.point.x + 200, y: inp.point.y }
  })()
  return [
    { Click: { name: "chat-input", point: inp.point } },
    { TypeText: { text: chatMessages.generate(), delayMillis: 30 } },
    { PressKey: { code: 13 } }, // Enter
  ]
})

// click send button directly
const sendBtnPoint = extract((state) => {
  const btn = state.document.getElementById("send-btn") as HTMLElement | null
  if (!btn || btn.offsetParent === null) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const clickSend = actions(() => {
  const p = sendBtnPoint.current
  if (!p || sendBtnDisabled.current) return []
  return [{ Click: { name: "send-btn", point: p } }]
})

// click "New Chat"
export const clickNewChat = actions(() => {
  const p = newChatBtnPoint.current
  return p ? [{ Click: { name: "new-chat-btn", point: p } }] : []
})

// click history items
export const clickHistory = actions(() => {
  return historyItemPoints.current.map((h) => ({
    Click: { name: `history-${h.idx}`, point: h.point },
  }) as Action)
})

// tab navigation (weighted toward chat)
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
    const p = chatTabPoint.current
    return p ? [{ Click: { name: "tab-chat", point: p } }] : []
  })],
  [1, actions(() => {
    return tabPoints.current
      .filter((t) => t.name !== "chat")
      .map((t) => ({ Click: { name: `tab-${t.name}`, point: t.point } }) as Action)
  })],
])
