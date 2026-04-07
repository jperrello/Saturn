import { initGraphicsOnLoad, initWelcomeSaturn } from './graphics.js'
import { initDiscover } from './discover.js'
import { loadServices, initServices } from './services.js'
import { initModels } from './models.js'
import { initChat } from './chat.js'
import { initTools } from './tools.js'
import { initConfigModule } from './config.js'
import { initSystem, loadSystemStatus } from './system.js'
import { initChatStars, updateIndicator } from './ui.js'

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    tab.classList.add('active')
    document.getElementById(tab.dataset.tab).classList.add('active')
    updateIndicator()
    document.getElementById('tools-panel')?.classList.add('hidden')
    document.getElementById('config-overlay')?.classList.add('hidden')
    if (tab.dataset.tab === 'chat') {
      const msgs = document.querySelector('.messages')
      if (msgs) initChatStars(msgs)
      initWelcomeSaturn()
    }
    if (tab.dataset.tab === 'system') loadSystemStatus()
  })
})
updateIndicator()

initDiscover()
initServices()
initModels()
initChat()
initTools()
initConfigModule()
initSystem()

// chat gate
function syncChatGate() {
  const accepted = localStorage.getItem('chat-accepted') === '1'
  document.getElementById('chat-gate').classList.toggle('hidden', accepted)
  document.getElementById('chat-shell').classList.toggle('hidden', !accepted)
}
syncChatGate()
document.getElementById('chat-accept').addEventListener('click', () => {
  localStorage.setItem('chat-accepted', '1')
  syncChatGate()
  initWelcomeSaturn()
})

window.addEventListener('load', initGraphicsOnLoad)
