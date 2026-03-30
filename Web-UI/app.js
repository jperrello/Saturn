// Toast (replaces alert() so automated testing doesn't freeze)
function toast(msg, ms = 3000) {
  const el = document.getElementById('toast')
  el.textContent = msg
  el.classList.remove('hidden')
  setTimeout(() => el.classList.add('hidden'), ms)
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    tab.classList.add('active')
    document.getElementById(tab.dataset.tab).classList.add('active')
  })
})

// ===== TEXTMODE.JS SATURN =====
// moons state — populated after discovery scan
window.saturnMoons = []

function initSaturn() {
  const container = document.getElementById('saturn-container')
  const fallback = document.getElementById('saturn-ascii')

  if (typeof textmode === 'undefined') return

  const w = container.clientWidth || 500
  const h = container.clientHeight || 500
  const fs = 14

  let t
  try {
    t = textmode.create({ width: w, height: h, fontSize: fs, frameRate: 24 })
  } catch (e) {
    return
  }

  const tmCanvas = t.canvas
  if (!tmCanvas) return
  container.appendChild(tmCanvas)
  fallback.style.display = 'none'

  const cols = Math.floor(w / fs)
  const rows = Math.floor(h / fs)
  const starChars = ['.', '*', '+', '·']

  const stars = []
  for (let i = 0; i < 50; i++) {
    stars.push({
      x: Math.floor(Math.random() * cols) - Math.floor(cols / 2),
      y: Math.floor(Math.random() * rows) - Math.floor(rows / 2),
      c: starChars[Math.floor(Math.random() * starChars.length)],
      phase: Math.random() * Math.PI * 2
    })
  }

  let frame = 0
  let discovering = false

  // 45-degree tilt angle
  const tilt = Math.PI / 4

  t.draw(() => {
    t.background(0)

    // stars
    stars.forEach(s => {
      const speed = discovering ? 0.15 : 0.02
      const base = discovering ? 80 : 40
      const range = discovering ? 120 : 30
      const b = base + range * Math.sin(frame * speed + s.phase)
      t.push()
      t.translate(s.x, s.y)
      t.char(s.c)
      t.charColor(b, b, b)
      t.point()
      t.pop()
    })

    // ring — drawn as individual points with gaps for transparency
    const ringRx = 18
    const ringRy = 3
    const ringGlow = discovering ? 100 + 155 * Math.abs(Math.sin(frame * 0.1)) : 180
    for (let a = 0; a < Math.PI * 2; a += 0.08) {
      const rx = Math.cos(a) * ringRx
      const ry = Math.sin(a) * ringRy
      // apply 45-degree tilt
      const px = rx * Math.cos(tilt) - ry * Math.sin(tilt)
      const py = rx * Math.sin(tilt) + ry * Math.cos(tilt)
      // skip points that would be behind the planet body
      const bodyRx = 9
      const bodyRy = 6
      const bx = px / bodyRx
      const by = py / bodyRy
      if (bx * bx + by * by < 0.7 && a > Math.PI * 0.3 && a < Math.PI * 1.2) continue
      // ring gap pattern
      if (Math.sin(a * 12) > 0.7) continue
      t.push()
      t.translate(Math.round(px), Math.round(py))
      t.char('═')
      if (discovering) {
        t.charColor(0, ringGlow, 0)
      } else {
        t.charColor(ringGlow, ringGlow * 0.7, ringGlow * 0.12)
      }
      t.point()
      t.pop()
    }

    // planet body
    const pGlow = discovering ? 240 + 15 * Math.sin(frame * 0.12) : 220
    t.char('█')
    t.charColor(pGlow, pGlow * 0.75, pGlow * 0.15)
    t.ellipse(9, 6)

    // front ring overlay (portion in front of planet)
    for (let a = Math.PI * 1.2; a < Math.PI * 2.3; a += 0.08) {
      const rx = Math.cos(a) * ringRx
      const ry = Math.sin(a) * ringRy
      const px = rx * Math.cos(tilt) - ry * Math.sin(tilt)
      const py = rx * Math.sin(tilt) + ry * Math.cos(tilt)
      const bx = px / 9
      const by = py / 6
      if (bx * bx + by * by < 0.8) {
        if (Math.sin(a * 12) > 0.7) continue
        t.push()
        t.translate(Math.round(px), Math.round(py))
        t.char('═')
        if (discovering) {
          t.charColor(0, ringGlow, 0)
        } else {
          t.charColor(ringGlow, ringGlow * 0.7, ringGlow * 0.12)
        }
        t.point()
        t.pop()
      }
    }

    // moons — one per online service
    window.saturnMoons.forEach((moon, i) => {
      const speed = 0.012 + i * 0.004
      const radius = 13 + i * 2
      const angle = frame * speed + (i * Math.PI * 2 / Math.max(window.saturnMoons.length, 1))
      const mx = Math.cos(angle) * radius
      const my = Math.sin(angle) * -(radius * 0.6)
      t.push()
      t.translate(Math.round(mx), Math.round(my))
      t.char('○')
      if (moon.selected) {
        t.charColor(0, 255, 0)
      } else {
        t.charColor(140, 140, 140)
      }
      t.point()
      t.pop()
    })

    // label
    const label = 'S A T U R N'
    for (let i = 0; i < label.length; i++) {
      t.push()
      t.translate(i - Math.floor(label.length / 2), 10)
      t.char(label[i])
      t.charColor(255, 255, 255)
      t.point()
      t.pop()
    }

    // scan line during discovery — GREEN
    if (discovering) {
      const scanY = (frame % rows) - Math.floor(rows / 2)
      t.char('─')
      t.charColor(0, 255, 0)
      t.push()
      t.translate(0, scanY)
      t.rect(cols, 1)
      t.pop()
    }

    frame++
  })

  window.saturnDiscover = (on) => { discovering = on }
}

window.addEventListener('load', () => {
  setTimeout(initSaturn, 300)
})

// ===== DISCOVER =====
let discoveredServices = []

function render(list, items, type) {
  list.innerHTML = ''
  items.forEach((s, i) => {
    const div = document.createElement('div')
    div.className = 'checklist-item'
    const statusClass = s.status === 'online' ? 'status-online' : 'status-offline'
    div.innerHTML = `
      <input type="checkbox" id="${type}-${i}">
      <span class="name">${s.name}</span>
      ${s.status ? `<span class="status ${statusClass}">${s.status}</span>` : ''}
    `
    // wire checkbox to moon selection
    const cb = div.querySelector('input[type="checkbox"]')
    cb.addEventListener('change', () => {
      const moon = window.saturnMoons.find(m => m.name === s.name)
      if (moon) moon.selected = cb.checked
    })
    list.appendChild(div)
  })
}

const discoverBtn = document.getElementById('discover-btn')
const servicesList = document.getElementById('services-list')

discoverBtn.addEventListener('click', async () => {
  discoverBtn.disabled = true
  discoverBtn.textContent = 'Scanning...'

  const left = document.querySelector('.discover-left')
  left.classList.add('discovering')
  if (window.saturnDiscover) window.saturnDiscover(true)

  try {
    const res = await fetch('/api/discover')
    discoveredServices = await res.json()
  } catch (e) {
    discoveredServices = []
    console.error('Discovery failed:', e)
  }

  window.saturnMoons = discoveredServices
    .filter(s => s.status === 'online')
    .map(s => ({ name: s.name, selected: false }))

  render(servicesList, discoveredServices, 'svc')
  syncServices()
  discoverBtn.textContent = 'Discover'
  discoverBtn.disabled = false
  left.classList.remove('discovering')
  if (window.saturnDiscover) window.saturnDiscover(false)
})

// ===== START TAB =====
let services = []

function statusBadge(s) {
  if (s.running) return '<span class="status-badge status-up">● RUNNING</span>'
  return '<span class="status-badge status-down">● STOPPED</span>'
}

function actionBtn(s) {
  if (s.running) {
    return `<button class="btn btn-stop" data-name="${s.name}">Stop</button>`
  }
  return `<button class="btn btn-start" data-name="${s.name}">Start</button>`
}

async function loadServices() {
  try {
    const res = await fetch('/api/services')
    services = await res.json()
  } catch (e) {
    services = []
    console.error('Failed to load services:', e)
  }
  renderServers()
}

function renderServers() {
  const list = document.getElementById('server-list')
  list.innerHTML = ''
  if (services.length === 0) {
    list.innerHTML = '<div class="checklist-item"><span class="name" style="color:var(--muted)">No services configured</span></div>'
    return
  }
  services.forEach(s => {
    const div = document.createElement('div')
    div.className = 'checklist-item'
    const tag = s.builtin ? '<span class="status-badge status-unknown">BUILT-IN</span>' : ''
    const info = s.port && s.running ? `<span class="status-badge" style="color:var(--muted)">:${s.port}</span>` : ''
    div.innerHTML = `
      <span class="name">${s.name}</span>
      <span class="status-badge" style="color:var(--muted)">${s.deployment} / ${s.api_type}</span>
      <span class="status-badge" style="color:var(--muted)">p${s.priority}</span>
      ${tag}
      ${info}
      ${statusBadge(s)}
      ${actionBtn(s)}
    `
    // wire start/stop buttons
    const btn = div.querySelector('.btn-start, .btn-stop')
    if (btn) {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation()
        btn.disabled = true
        btn.textContent = s.running ? 'Stopping...' : 'Starting...'
        try {
          const endpoint = s.running ? `/api/services/${s.name}/stop` : `/api/services/${s.name}/start`
          const res = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
          if (!res.ok) {
            const err = await res.json()
            toast(err.detail || 'Operation failed')
          }
        } catch (e) {
          console.error(e)
        }
        await loadServices()
      })
    }
    list.appendChild(div)
  })
}

// skip password gate — go straight to server panel
document.getElementById('password-gate').classList.add('hidden')
document.getElementById('server-panel').classList.remove('hidden')
loadServices()

document.getElementById('config-btn').addEventListener('click', () => {
  document.getElementById('server-panel').classList.add('hidden')
  document.getElementById('config-page').classList.remove('hidden')
  initConfigStars()
})

document.getElementById('cfg-back').addEventListener('click', () => {
  document.getElementById('config-page').classList.add('hidden')
  document.getElementById('server-panel').classList.remove('hidden')
})

// Deployment toggle — show/hide cloud vs network fields
const deploySelect = document.getElementById('cfg-deployment')
const cloudFields = document.getElementById('cloud-fields')
const networkFields = document.getElementById('network-fields')
const testBtn = document.getElementById('cfg-test')

deploySelect.addEventListener('change', () => {
  const cloud = deploySelect.value === 'cloud'
  cloudFields.classList.toggle('hidden', !cloud)
  networkFields.classList.toggle('hidden', cloud)
  testBtn.classList.toggle('hidden', cloud)
})

// Ephemeral keys toggle
document.getElementById('cfg-ephemeral').addEventListener('change', (e) => {
  document.getElementById('ephemeral-fields').classList.toggle('hidden', !e.target.checked)
})

// Test connection
testBtn.addEventListener('click', async () => {
  const baseUrl = document.getElementById('cfg-base-url').value
  if (!baseUrl) return
  testBtn.disabled = true
  testBtn.textContent = 'Testing...'
  try {
    const res = await fetch(baseUrl.replace(/\/+$/, '') + '/models', { signal: AbortSignal.timeout(5000) })
    testBtn.textContent = res.ok ? 'Connection OK' : `Error ${res.status}`
  } catch (e) {
    testBtn.textContent = 'Failed'
  }
  setTimeout(() => { testBtn.textContent = 'Test Connection'; testBtn.disabled = false }, 2000)
})

// Save — creates a real service config via API
document.getElementById('cfg-save').addEventListener('click', async () => {
  const name = document.getElementById('cfg-name').value.trim()
  const baseUrl = document.getElementById('cfg-base-url').value.trim()
  if (!name || !baseUrl) return

  const body = {
    name,
    deployment: document.getElementById('cfg-deployment').value,
    api_type: document.getElementById('cfg-api-type').value,
    priority: parseInt(document.getElementById('cfg-priority').value) || 50,
    base_url: baseUrl,
    api_key_env: document.getElementById('cfg-api-key').value.trim() || null,
    port: parseInt(document.getElementById('cfg-adv-port').value) || 0,
    beacon_enabled: document.getElementById('cfg-ephemeral').checked,
    beacon_provider: document.getElementById('cfg-keygen-url').value.trim() || null,
    rotation_interval: parseInt(document.getElementById('cfg-rotation').value) || 300,
    expiration_interval: parseInt(document.getElementById('cfg-expiration').value) || 600,
  }

  try {
    const res = await fetch('/api/services', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json()
      toast(err.detail || 'Failed to create service')
      return
    }
  } catch (e) {
    toast('Failed to create service')
    return
  }

  resetConfigForm()
  document.getElementById('config-page').classList.add('hidden')
  document.getElementById('server-panel').classList.remove('hidden')
  await loadServices()
})

function resetConfigForm() {
  document.getElementById('cfg-name').value = ''
  document.getElementById('cfg-base-url').value = ''
  document.getElementById('cfg-deployment').value = 'cloud'
  document.getElementById('cfg-api-type').value = 'openai'
  document.getElementById('cfg-enabled').checked = true
  document.getElementById('cfg-priority').value = '10'
  document.getElementById('cfg-adv-port').value = ''
  document.getElementById('cfg-api-key').value = ''
  document.getElementById('cfg-ephemeral').checked = false
  document.getElementById('cfg-keygen-url').value = ''
  document.getElementById('cfg-spend-limit').value = '0'
  document.getElementById('cfg-rotation').value = '300'
  document.getElementById('cfg-expiration').value = '600'
  document.getElementById('cfg-host').value = ''
  document.getElementById('cfg-net-port').value = ''
  cloudFields.classList.remove('hidden')
  networkFields.classList.add('hidden')
  testBtn.classList.add('hidden')
  document.getElementById('ephemeral-fields').classList.add('hidden')
}

// Config page star field (canvas)
let configAnimId = null
function initConfigStars() {
  if (configAnimId) cancelAnimationFrame(configAnimId)
  const canvas = document.getElementById('config-canvas')
  const container = document.getElementById('config-stars')
  const w = container.clientWidth || 500
  const h = container.clientHeight || 500
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')

  const stars = []
  for (let i = 0; i < 80; i++) {
    stars.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.5 + 0.5,
      phase: Math.random() * Math.PI * 2
    })
  }

  let frame = 0
  function draw() {
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    stars.forEach(s => {
      const b = 40 + 30 * Math.sin(frame * 0.02 + s.phase)
      const v = Math.round(b)
      ctx.fillStyle = `rgb(${v},${v},${v})`
      ctx.beginPath()
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
      ctx.fill()
    })
    frame++
    configAnimId = requestAnimationFrame(draw)
  }
  draw()
}

// ===== CHAT =====
const messagesEl = document.getElementById('messages')
const welcome = document.getElementById('welcome')
const input = document.getElementById('chat-input')
const sendBtn = document.getElementById('send-btn')
const historyList = document.getElementById('history-list')
const serviceSelect = document.getElementById('service-select')
const modelSelect = document.getElementById('model-select')

const chats = []
let activeChat = null
let sending = false

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// populate service dropdown from discovered services
function syncServices() {
  const prev = serviceSelect.value
  serviceSelect.innerHTML = ''
  if (discoveredServices.length === 0) {
    serviceSelect.innerHTML = '<option value="" disabled selected>-- discover first --</option>'
    return
  }
  discoveredServices.forEach(s => {
    const opt = document.createElement('option')
    opt.value = s.name
    opt.textContent = `⊙ ${s.name}`
    serviceSelect.appendChild(opt)
  })
  // restore previous selection if still available
  if (prev && [...serviceSelect.options].some(o => o.value === prev)) {
    serviceSelect.value = prev
  }
  loadModels()
}

// fetch models from selected service
async function loadModels() {
  const name = serviceSelect.value
  if (!name) {
    modelSelect.innerHTML = '<option value="" disabled selected>-- select service --</option>'
    return
  }
  modelSelect.innerHTML = '<option value="" disabled selected>loading...</option>'
  try {
    const res = await fetch(`/api/models?service=${encodeURIComponent(name)}`)
    const list = await res.json()
    modelSelect.innerHTML = ''
    if (list.length === 0) {
      modelSelect.innerHTML = '<option value="" disabled selected>-- no models --</option>'
      return
    }
    list.forEach(m => {
      const opt = document.createElement('option')
      opt.value = m.id
      opt.textContent = m.id
      modelSelect.appendChild(opt)
    })
  } catch {
    modelSelect.innerHTML = '<option value="" disabled selected>-- error --</option>'
  }
}

serviceSelect.addEventListener('change', loadModels)

// auto-refresh models every 30s (same pattern as omlx-saturn chat.html)
setInterval(() => {
  if (serviceSelect.value) loadModels()
}, 30000)

function renderMessages() {
  messagesEl.querySelectorAll('.msg').forEach(m => m.remove())
  if (activeChat === null || chats[activeChat].messages.length === 0) {
    welcome.classList.remove('hidden')
    return
  }
  welcome.classList.add('hidden')
  chats[activeChat].messages.forEach(m => {
    const div = document.createElement('div')
    if (m.role === 'user') {
      div.className = 'msg user'
      div.innerHTML = `<div class="prefix">&gt; you</div><div class="bubble">${esc(m.text)}</div>`
    } else {
      div.className = 'msg assistant'
      div.innerHTML = `
        <div class="meta">${m.service || ''} // ${m.model || ''}</div>
        <div class="bubble">${esc(m.text)}</div>
      `
    }
    messagesEl.appendChild(div)
  })
  messagesEl.scrollTop = messagesEl.scrollHeight
}

function renderHistory() {
  historyList.innerHTML = ''
  chats.forEach((c, i) => {
    const li = document.createElement('li')
    li.className = 'history-item' + (i === activeChat ? ' active' : '')
    li.dataset.chat = i
    li.textContent = c.name.slice(0, 20) + (c.name.length > 20 ? '...' : '')
    li.addEventListener('click', () => loadChat(i))
    historyList.appendChild(li)
  })
}

function loadChat(idx) {
  activeChat = idx
  renderHistory()
  renderMessages()
}

function newChat() {
  chats.unshift({ name: 'New Chat', messages: [] })
  loadChat(0)
}

// stream chat completions from saturn service — mirrors omlx saturn proxy pattern
async function send() {
  const text = input.value.trim()
  if (!text || sending) return
  input.value = ''

  const service = serviceSelect.value
  const model = modelSelect.value
  if (!service || !model) {
    toast('Select a service and model first (run Discover)')
    return
  }

  if (activeChat === null) newChat()
  const chat = chats[activeChat]

  if (chat.messages.length === 0) {
    chat.name = text.slice(0, 20) + (text.length > 20 ? '...' : '')
    renderHistory()
  }

  chat.messages.push({ role: 'user', text })
  welcome.classList.add('hidden')

  const userDiv = document.createElement('div')
  userDiv.className = 'msg user'
  userDiv.innerHTML = `<div class="prefix">&gt; you</div><div class="bubble">${esc(text)}</div>`
  messagesEl.appendChild(userDiv)
  messagesEl.scrollTop = messagesEl.scrollHeight

  // build OpenAI-format messages array
  const apiMessages = chat.messages
    .filter(m => m.role === 'user' || m.role === 'assistant')
    .map(m => ({ role: m.role, content: m.text }))

  // create assistant placeholder with streaming cursor
  const aDiv = document.createElement('div')
  aDiv.className = 'msg assistant'
  aDiv.innerHTML = `
    <div class="meta">${esc(service)} // ${esc(model)}</div>
    <div class="bubble"><span class="cursor">▊</span></div>
  `
  messagesEl.appendChild(aDiv)
  messagesEl.scrollTop = messagesEl.scrollHeight

  const bubble = aDiv.querySelector('.bubble')
  let full = ''
  sending = true
  sendBtn.disabled = true

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service, model, messages: apiMessages }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      full = `[error] ${err.error || res.statusText}`
      bubble.innerHTML = esc(full)
      chat.messages.push({ role: 'assistant', text: full, service, model })
      return
    }

    // parse SSE stream — same text/event-stream format as omlx
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') break

        try {
          const chunk = JSON.parse(data)
          const delta = chunk.choices?.[0]?.delta?.content
          if (delta) {
            full += delta
            bubble.innerHTML = esc(full) + '<span class="cursor">▊</span>'
            messagesEl.scrollTop = messagesEl.scrollHeight
          }
        } catch {
          // skip malformed chunks
        }
      }
    }

    // remove cursor, finalize
    bubble.innerHTML = esc(full || '[empty response]')
    chat.messages.push({ role: 'assistant', text: full || '[empty response]', service, model })
  } catch (e) {
    full = `[error] ${e.message}`
    bubble.innerHTML = esc(full)
    chat.messages.push({ role: 'assistant', text: full, service, model })
  } finally {
    sending = false
    sendBtn.disabled = false
  }
}

document.getElementById('new-chat-btn').addEventListener('click', newChat)
sendBtn.addEventListener('click', send)
input.addEventListener('keydown', e => { if (e.key === 'Enter') send() })

document.querySelectorAll('.example').forEach(ex => {
  ex.addEventListener('click', () => {
    input.value = ex.textContent
    send()
  })
})

renderHistory()

// ===== BRUTUS =====
const brutusGate = document.getElementById('brutus-gate')
const brutusMain = document.getElementById('brutus-main')
const brutusMessages = document.getElementById('brutus-messages')
const brutusWelcome = document.getElementById('brutus-welcome')
const brutusInput = document.getElementById('brutus-input')
const brutusSend = document.getElementById('brutus-send')
const brutusStatus = document.getElementById('brutus-status')
let brutusSending = false
let brutusHistory = []

// gate acceptance
document.getElementById('brutus-accept').addEventListener('click', () => {
  brutusGate.classList.add('hidden')
  brutusMain.classList.remove('hidden')
  localStorage.setItem('brutus-accepted', '1')
  loadBrutusQR()
  loadBrutusBackends()
})

// restore gate state
if (localStorage.getItem('brutus-accepted') === '1') {
  brutusGate.classList.add('hidden')
  brutusMain.classList.remove('hidden')
}

// hash-based deep link (for QR code scans)
function checkHash() {
  if (location.hash === '#brutus') {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    document.querySelector('[data-tab="brutus"]').classList.add('active')
    document.getElementById('brutus').classList.add('active')
  }
}
window.addEventListener('hashchange', checkHash)
checkHash()

// QR code
const tunnelStatus = document.getElementById('brutus-tunnel-status')
const tunnelStartBtn = document.getElementById('brutus-tunnel-start')
const tunnelStopBtn = document.getElementById('brutus-tunnel-stop')

function renderQR(url) {
  const container = document.getElementById('brutus-qr')
  const urlText = document.getElementById('brutus-url')
  if (!url) {
    container.innerHTML = ''
    urlText.textContent = 'No tunnel active'
    return
  }
  const target = url.replace(/\/$/, '') + '/#brutus'
  urlText.textContent = target

  if (typeof qrcode === 'undefined') return
  const qr = qrcode(0, 'M')
  qr.addData(target)
  qr.make()
  container.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0 })
  const svg = container.querySelector('svg')
  if (svg) {
    svg.style.width = '100%'
    svg.style.maxWidth = '200px'
    svg.querySelectorAll('rect').forEach(r => {
      const fill = r.getAttribute('fill')
      if (fill === '#000000') r.setAttribute('fill', '#ffffff')
      else if (fill === '#ffffff') r.setAttribute('fill', '#000000')
    })
  }
}

function setTunnelUI(status, url) {
  if (status === 'running') {
    tunnelStatus.textContent = '● tunnel active'
    tunnelStatus.style.color = 'var(--green)'
    tunnelStartBtn.classList.add('hidden')
    tunnelStopBtn.classList.remove('hidden')
    renderQR(url)
  } else {
    tunnelStatus.textContent = '● stopped'
    tunnelStatus.style.color = 'var(--red)'
    tunnelStartBtn.classList.remove('hidden')
    tunnelStopBtn.classList.add('hidden')
    renderQR(null)
  }
}

async function loadBrutusQR() {
  try {
    const res = await fetch('/api/brutus/tunnel/status')
    const data = await res.json()
    if (data.status === 'running' && data.url) {
      setTunnelUI('running', data.url)
      return
    }
  } catch { /* fall through */ }
  // show LAN fallback QR
  try {
    const res = await fetch('/api/brutus/url')
    const data = await res.json()
    tunnelStatus.textContent = '● lan only'
    tunnelStatus.style.color = 'var(--muted)'
    renderQR(data.url)
  } catch {
    renderQR(null)
  }
}

// start tunnel
tunnelStartBtn.addEventListener('click', async () => {
  tunnelStartBtn.disabled = true
  tunnelStartBtn.textContent = 'Starting...'
  tunnelStatus.textContent = '● connecting...'
  tunnelStatus.style.color = 'var(--accent)'
  try {
    const res = await fetch('/api/brutus/tunnel/start', { method: 'POST' })
    const data = await res.json()
    if (data.url) {
      setTunnelUI('running', data.url)
    } else {
      toast(data.error || 'Tunnel failed to start')
      setTunnelUI('stopped')
    }
  } catch (e) {
    toast('Failed to start tunnel: ' + e.message)
    setTunnelUI('stopped')
  } finally {
    tunnelStartBtn.disabled = false
    tunnelStartBtn.textContent = 'Start Tunnel'
  }
})

// stop tunnel
tunnelStopBtn.addEventListener('click', async () => {
  tunnelStopBtn.disabled = true
  tunnelStopBtn.textContent = 'Stopping...'
  try {
    await fetch('/api/brutus/tunnel/stop', { method: 'POST' })
  } catch { /* ok */ }
  setTunnelUI('stopped')
  tunnelStopBtn.disabled = false
  tunnelStopBtn.textContent = 'Stop Tunnel'
  // show LAN fallback
  await loadBrutusQR()
})

// LAN only button
document.getElementById('brutus-qr-refresh').addEventListener('click', async () => {
  try {
    const res = await fetch('/api/brutus/url')
    const data = await res.json()
    tunnelStatus.textContent = '● lan only'
    tunnelStatus.style.color = 'var(--muted)'
    renderQR(data.url)
  } catch {
    renderQR(null)
  }
})

// backend status display
async function loadBrutusBackends() {
  const container = document.getElementById('brutus-backends')
  if (discoveredServices.length === 0) {
    container.innerHTML = '<div class="brutus-backend-item"><span class="name" style="color:var(--muted)">Run Discover first</span></div>'
    return
  }
  container.innerHTML = ''
  discoveredServices.forEach(s => {
    const div = document.createElement('div')
    div.className = 'brutus-backend-item'
    const icon = s.status === 'online' ? '●' : '○'
    const color = s.status === 'online' ? 'var(--green)' : 'var(--red)'
    div.innerHTML = `<span style="color:${color}">${icon}</span> <span class="name">${s.name}</span> <span style="color:var(--muted)">p${s.priority}</span>`
    container.appendChild(div)
  })
}

// refresh when tab shown
document.querySelector('[data-tab="brutus"]').addEventListener('click', () => {
  if (!brutusMain.classList.contains('hidden')) {
    loadBrutusQR()
    loadBrutusBackends()
  }
})

// clear
document.getElementById('brutus-clear').addEventListener('click', () => {
  brutusHistory = []
  brutusMessages.querySelectorAll('.msg').forEach(m => m.remove())
  brutusWelcome.classList.remove('hidden')
})

// send message through brutus
async function brutusSendMsg() {
  const text = brutusInput.value.trim()
  if (!text || brutusSending) return
  brutusInput.value = ''

  brutusWelcome.classList.add('hidden')
  brutusHistory.push({ role: 'user', content: text })

  const userDiv = document.createElement('div')
  userDiv.className = 'msg user'
  userDiv.innerHTML = `<div class="prefix">&gt; you</div><div class="bubble">${esc(text)}</div>`
  brutusMessages.appendChild(userDiv)
  brutusMessages.scrollTop = brutusMessages.scrollHeight

  const aDiv = document.createElement('div')
  aDiv.className = 'msg assistant'
  aDiv.innerHTML = `
    <div class="meta">brutus // routing...</div>
    <div class="bubble"><span class="cursor">▊</span></div>
  `
  brutusMessages.appendChild(aDiv)
  brutusMessages.scrollTop = brutusMessages.scrollHeight

  const meta = aDiv.querySelector('.meta')
  const bubble = aDiv.querySelector('.bubble')
  let full = ''
  brutusSending = true
  brutusSend.disabled = true
  brutusStatus.textContent = '● streaming'
  brutusStatus.style.color = 'var(--accent)'

  try {
    const res = await fetch('/api/brutus/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: brutusHistory }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      full = `[error] ${err.error || res.statusText}`
      bubble.innerHTML = esc(full)
      brutusHistory.push({ role: 'assistant', content: full })
      syncBrutusToChat(text, full, 'brutus', '?')
      return
    }

    const service = res.headers.get('X-Brutus-Service') || 'unknown'
    const model = res.headers.get('X-Brutus-Model') || 'auto'
    meta.textContent = `brutus → ${service} // ${model}`

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') break
        try {
          const chunk = JSON.parse(data)
          const delta = chunk.choices?.[0]?.delta?.content
          if (delta) {
            full += delta
            bubble.innerHTML = esc(full) + '<span class="cursor">▊</span>'
            brutusMessages.scrollTop = brutusMessages.scrollHeight
          }
        } catch { /* skip */ }
      }
    }

    bubble.innerHTML = esc(full || '[empty response]')
    const reply = full || '[empty response]'
    brutusHistory.push({ role: 'assistant', content: reply })
    syncBrutusToChat(text, reply, service, model)
  } catch (e) {
    full = `[error] ${e.message}`
    bubble.innerHTML = esc(full)
    brutusHistory.push({ role: 'assistant', content: full })
    syncBrutusToChat(text, full, 'brutus', '?')
  } finally {
    brutusSending = false
    brutusSend.disabled = false
    brutusStatus.textContent = '● idle'
    brutusStatus.style.color = 'var(--green)'
  }
}

// sync brutus conversations into Chat tab history
function syncBrutusToChat(userText, assistantText, service, model) {
  let idx = chats.findIndex(c => c.name === 'Brutus')
  if (idx === -1) {
    chats.unshift({ name: 'Brutus', messages: [] })
    idx = 0
  }
  chats[idx].messages.push({ role: 'user', text: userText })
  chats[idx].messages.push({ role: 'assistant', text: assistantText, service, model })
  renderHistory()
}

brutusSend.addEventListener('click', brutusSendMsg)
brutusInput.addEventListener('keydown', e => { if (e.key === 'Enter') brutusSendMsg() })

document.querySelectorAll('.brutus-example').forEach(ex => {
  ex.addEventListener('click', () => {
    brutusInput.value = ex.textContent
    brutusSendMsg()
  })
})
