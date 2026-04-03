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

// re-export default safety properties
export { noUncaughtExceptions, noUnhandledPromiseRejections }
export { scroll }

// --- extractors ---

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

const pageCount = extract((state) =>
  state.document.querySelectorAll(".page").length
)

const hasOverflowingContent = extract((state) => {
  const app = state.document.querySelector(".app") as HTMLElement | null
  if (!app) return false
  return app.scrollWidth > state.window.innerWidth + 10
})

// --- properties ---

// exactly 4 tabs always exist (discover, start, chat, brutus)
export const fourTabsExist = always(() => tabCount.current === 4)

// exactly 4 pages always exist
export const fourPagesExist = always(() => pageCount.current === 4)

// active tab and active page always match
export const tabMatchesPage = always(() => activeTab.current === activePage.current)

// one tab is always active
export const oneTabActive = always(() => activeTab.current !== null)

// no horizontal overflow
export const noOverflow = always(() => !hasOverflowingContent.current)

// --- actions ---

// click each tab
const tabDiscover = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="discover"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const tabStart = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="start"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const tabChat = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="chat"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

const tabBrutus = extract((state) => {
  const btn = state.document.querySelector('.tab[data-tab="brutus"]') as HTMLElement | null
  if (!btn) return null
  const r = btn.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
})

export const tabNavigation = actions(() => {
  const result: Action[] = []
  const d = tabDiscover.current
  const s = tabStart.current
  const c = tabChat.current
  const b = tabBrutus.current
  if (d) result.push({ Click: { name: "tab-discover", point: d } })
  if (s) result.push({ Click: { name: "tab-start", point: s } })
  if (c) result.push({ Click: { name: "tab-chat", point: c } })
  if (b) result.push({ Click: { name: "tab-brutus", point: b } })
  return result
})
