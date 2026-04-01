import * as THREE from 'three'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'

// Toast (replaces alert() so automated testing doesn't freeze)
function toast(msg, ms = 3000) {
  const el = document.getElementById('toast')
  el.textContent = msg
  el.classList.remove('hidden')
  setTimeout(() => el.classList.add('hidden'), ms)
}

// Chat star field background
function initChatStars(container) {
  if (container.querySelector('canvas.bg-stars')) return
  const canvas = document.createElement('canvas')
  canvas.className = 'bg-stars'
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0'
  container.style.position = 'relative'
  container.insertBefore(canvas, container.firstChild)
  const ctx = canvas.getContext('2d')
  const stars = Array.from({length: 120}, () => ({
    x: Math.random(), y: Math.random(),
    r: 0.5 + Math.random() * 1.5,
    dy: 0.00002 + Math.random() * 0.0001,
    phase: Math.random() * Math.PI * 2
  }))
  let frame = 0
  setInterval(() => {
    if (!document.getElementById('chat')?.classList.contains('active')) return
    canvas.width = container.clientWidth
    canvas.height = container.clientHeight
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    frame++
    for (const s of stars) {
      s.y = (s.y + s.dy) % 1
      const alpha = 0.3 + 0.3 * Math.sin(frame * 0.02 + s.phase)
      ctx.fillStyle = `rgba(255,255,255,${alpha})`
      ctx.beginPath()
      ctx.arc(s.x * canvas.width, s.y * canvas.height, s.r, 0, Math.PI * 2)
      ctx.fill()
    }
  }, 33)
}

// Mini Saturn for chat welcome
function initWelcomeSaturn() {
  const container = document.getElementById('welcome-saturn')
  if (!container || container.querySelector('canvas')) return

  const w = container.clientWidth || 240, h = container.clientHeight || 180
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100)
  camera.position.set(0, 0.4, 5.5)
  camera.lookAt(0, -0.1, 0)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 0)
  container.appendChild(renderer.domElement)

  // planet particles
  const pCount = 5000
  const pPos = new Float32Array(pCount * 3)
  const golden = Math.PI * (3 - Math.sqrt(5))
  for (let i = 0; i < pCount; i++) {
    const y = 1 - (i / (pCount - 1)) * 2
    const r = Math.sqrt(1 - y * y)
    const theta = golden * i
    pPos[i * 3] = Math.cos(theta) * r
    pPos[i * 3 + 1] = y
    pPos[i * 3 + 2] = Math.sin(theta) * r
  }
  const pGeo = new THREE.BufferGeometry()
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3))
  const pMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      uniform float uTime;
      varying float vBright;
      varying float vFresnel;
      void main() {
        vec3 norm = normalize(position);
        vec3 light = normalize(vec3(0.15, -0.3, 0.9));
        float wrap = 0.3;
        vBright = max(0.1, (dot(norm, light) + wrap) / (1.0 + wrap));
        vBright *= 0.85 + 0.15 * sin(norm.y * 22.0 + uTime * 0.5);
        vec3 viewDir = normalize(cameraPosition - (modelMatrix * vec4(position, 1.0)).xyz);
        vec3 worldNorm = normalize((modelMatrix * vec4(norm, 0.0)).xyz);
        vFresnel = pow(1.0 - max(dot(worldNorm, viewDir), 0.0), 3.0);
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.5, 4.5 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      varying float vBright;
      varying float vFresnel;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float glow = 1.0 - d * 2.0;
        glow = glow * glow;
        vec3 col = vec3(0.94, 0.71, 0.16) * vBright;
        col += vec3(0.7, 0.5, 0.15) * vFresnel * 0.6;
        col += col * glow * 0.4;
        gl_FragColor = vec4(col, 0.7 + glow * 0.3);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  })
  const planet = new THREE.Points(pGeo, pMat)
  planet.rotation.x = 0.35
  scene.add(planet)

  // ring particles
  const rCount = 5000
  const rPos = new Float32Array(rCount * 3)
  for (let i = 0; i < rCount; i++) {
    const angle = Math.random() * Math.PI * 2
    const r = 1.4 + Math.random() * 0.9
    if (Math.abs(r - 1.75) < 0.06) {
      rPos[i * 3] = rPos[i * 3 + 1] = rPos[i * 3 + 2] = 0
    } else {
      rPos[i * 3] = Math.cos(angle) * r
      rPos[i * 3 + 1] = (Math.random() - 0.5) * 0.03
      rPos[i * 3 + 2] = Math.sin(angle) * r
    }
  }
  const rGeo = new THREE.BufferGeometry()
  rGeo.setAttribute('position', new THREE.BufferAttribute(rPos, 3))
  const rMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      uniform float uTime;
      varying float vBright;
      void main() {
        float dist = length(position.xz);
        float t = (dist - 1.4) / 0.9;
        vBright = 0.3 + 0.7 * (1.0 - t);
        vBright *= 0.88 + 0.12 * sin(dist * 14.0 + uTime * 0.3);
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.5, 4.5 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      varying float vBright;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float glow = 1.0 - d * 2.0;
        glow = glow * glow;
        vec3 col = vec3(0.92, 0.72, 0.28) * vBright;
        col += col * glow * 0.5;
        gl_FragColor = vec4(col, 0.75 + glow * 0.25);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  })
  const rings = new THREE.Points(rGeo, rMat)
  rings.rotation.x = 0.35
  scene.add(rings)

  // stars
  const sCount = 200
  const sPos = new Float32Array(sCount * 3)
  const sPhase = new Float32Array(sCount)
  for (let i = 0; i < sCount; i++) {
    sPos[i * 3] = (Math.random() - 0.5) * 25
    sPos[i * 3 + 1] = (Math.random() - 0.5) * 25
    sPos[i * 3 + 2] = -10 - Math.random() * 15
    sPhase[i] = Math.random() * Math.PI * 2
  }
  const sGeo = new THREE.BufferGeometry()
  sGeo.setAttribute('position', new THREE.BufferAttribute(sPos, 3))
  sGeo.setAttribute('aPhase', new THREE.BufferAttribute(sPhase, 1))
  const sMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      attribute float aPhase;
      varying float vPhase;
      void main() {
        vPhase = aPhase;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.0, 2.0 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      varying float vPhase;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float twinkle = 0.3 + 0.7 * abs(sin(uTime * 0.5 + vPhase));
        gl_FragColor = vec4(vec3(twinkle), 1.0);
      }
    `,
    transparent: true,
    depthWrite: false
  })
  scene.add(new THREE.Points(sGeo, sMat))

  const clock = new THREE.Clock()
  let raf
  function animate() {
    raf = requestAnimationFrame(animate)
    const t = clock.getElapsedTime()
    planet.rotation.y = t * 0.08
    rings.rotation.y = t * 0.05
    pMat.uniforms.uTime.value = t
    rMat.uniforms.uTime.value = t
    sMat.uniforms.uTime.value = t
    renderer.render(scene, camera)
  }
  animate()

  const ro = new ResizeObserver(() => {
    const cw = container.clientWidth, ch = container.clientHeight
    if (cw === 0 || ch === 0) return
    camera.aspect = cw / ch
    camera.updateProjectionMatrix()
    renderer.setSize(cw, ch)
  })
  ro.observe(container)

  return () => { cancelAnimationFrame(raf); renderer.dispose() }
}

// Brutus matrix rain background
function initBrutusRain(container) {
  if (container.querySelector('canvas.bg-rain')) return
  const canvas = document.createElement('canvas')
  canvas.className = 'bg-rain'
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;opacity:0.07'
  container.style.position = 'relative'
  container.insertBefore(canvas, container.firstChild)
  const ctx = canvas.getContext('2d')
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%^&*'
  let columns = []
  function resize() {
    canvas.width = container.clientWidth
    canvas.height = container.clientHeight
    const colW = 14
    const count = Math.ceil(canvas.width / colW)
    columns = Array.from({length: count}, (_, i) => ({
      x: i * colW,
      y: Math.random() * canvas.height,
      speed: 1 + Math.random() * 3
    }))
  }
  resize()
  window.addEventListener('resize', resize)
  setInterval(() => {
    if (!document.getElementById('brutus')?.classList.contains('active')) return
    ctx.fillStyle = 'rgba(0, 0, 0, 0.1)'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#4ade80'
    ctx.font = '12px monospace'
    for (const col of columns) {
      ctx.fillText(chars[Math.floor(Math.random() * chars.length)], col.x, col.y)
      col.y += col.speed * 12
      if (col.y > canvas.height) col.y = 0
    }
  }, 66)
}

// Code block copy buttons
function addCopyButtons(container) {
  container.querySelectorAll('pre').forEach(pre => {
    if (pre.querySelector('.code-copy')) return
    const code = pre.querySelector('code')
    if (code) {
      const lang = [...code.classList].find(c => c.startsWith('language-'))
      if (lang) pre.setAttribute('data-lang', lang.replace('language-', ''))
    }
    const btn = document.createElement('button')
    btn.className = 'code-copy'
    btn.textContent = '[COPY]'
    btn.onclick = () => {
      navigator.clipboard.writeText(pre.textContent)
      btn.textContent = '[COPIED]'
      setTimeout(() => btn.textContent = '[COPY]', 1500)
    }
    pre.style.position = 'relative'
    pre.appendChild(btn)
  })
}

// Tab indicator
const tabIndicator = document.createElement('div')
tabIndicator.className = 'tab-indicator'
tabIndicator.style.cssText = 'position:absolute;bottom:0;height:3px;background:var(--accent);transition:left 0.3s cubic-bezier(0.4,0,0.2,1),width 0.3s cubic-bezier(0.4,0,0.2,1)'
document.querySelector('.tabs').style.position = 'relative'
document.querySelector('.tabs').appendChild(tabIndicator)

function updateIndicator() {
  const active = document.querySelector('.tab.active')
  if (active) {
    tabIndicator.style.left = active.offsetLeft + 'px'
    tabIndicator.style.width = active.offsetWidth + 'px'
  }
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    tab.classList.add('active')
    document.getElementById(tab.dataset.tab).classList.add('active')
    updateIndicator()
    // init canvas backgrounds on tab switch
    if (tab.dataset.tab === 'chat') {
      const msgs = document.querySelector('.messages')
      if (msgs) initChatStars(msgs)
      initWelcomeSaturn()
    }
    if (tab.dataset.tab === 'brutus') {
      const dash = document.querySelector('.brutus-dashboard-col')
      if (dash) initBrutusRain(dash)
    }
  })
})
updateIndicator()

// ===== CHROMATIC ABERRATION SHADER =====
const ChromaticAberrationShader = {
  uniforms: {
    tDiffuse: { value: null },
    uAmount: { value: 0.003 },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uAmount;
    varying vec2 vUv;
    void main() {
      vec2 dir = normalize(vUv - 0.5 + 0.001);
      float dist = length(vUv - 0.5);
      vec2 offset = dir * uAmount * dist;
      float r = texture2D(tDiffuse, vUv + offset).r;
      float g = texture2D(tDiffuse, vUv).g;
      float b = texture2D(tDiffuse, vUv - offset).b;
      gl_FragColor = vec4(r, g, b, 1.0);
    }
  `
}

// ===== BRIGHTNESS CLAMP SHADER (pre-bloom) =====
const BrightnessClampShader = {
  uniforms: {
    tDiffuse: { value: null },
    uMax: { value: 1.2 },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uMax;
    varying vec2 vUv;
    void main() {
      vec4 col = texture2D(tDiffuse, vUv);
      col.rgb = min(col.rgb, vec3(uMax));
      gl_FragColor = col;
    }
  `
}

// ===== FILM GRAIN + SCANLINES SHADER =====
const FilmGrainShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uGrainIntensity: { value: 0.035 },
    uScanlineOpacity: { value: 0.0 },
    uVignetteStrength: { value: 0.25 },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform float uGrainIntensity;
    uniform float uScanlineOpacity;
    uniform float uVignetteStrength;
    varying vec2 vUv;

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    void main() {
      vec4 col = texture2D(tDiffuse, vUv);

      // film grain
      float grain = hash(vUv * 1000.0 + uTime * 100.0) * 2.0 - 1.0;
      col.rgb += grain * uGrainIntensity;

      // scanlines
      float scanline = step(0.5, fract(gl_FragCoord.y / 4.0));
      col.rgb -= scanline * uScanlineOpacity;

      // vignette
      vec2 uv = vUv * (1.0 - vUv);
      float vig = uv.x * uv.y * 15.0;
      vig = pow(vig, uVignetteStrength);
      col.rgb *= vig;

      gl_FragColor = col;
    }
  `
}

// ===== 3D PARTICLE SATURN =====
window.saturnMoons = []

function initSaturn() {
  const container = document.getElementById('saturn-container')
  container.innerHTML = ''

  const w = container.clientWidth, h = container.clientHeight
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100)
  camera.position.set(0, 0.4, 6.5)
  camera.lookAt(0, -0.15, 0)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 1)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)

  // post-processing
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))

  const clampPass = new ShaderPass(BrightnessClampShader)
  composer.addPass(clampPass)

  const bloom = new UnrealBloomPass(
    new THREE.Vector2(w, h),
    1.8,   // strength
    0.5,   // radius
    0.55   // threshold
  )
  composer.addPass(bloom)

  const chromaPass = new ShaderPass(ChromaticAberrationShader)
  composer.addPass(chromaPass)

  const filmPass = new ShaderPass(FilmGrainShader)
  composer.addPass(filmPass)

  composer.addPass(new OutputPass())

  // pointer tracking (unified mouse + touch)
  const mouse = new THREE.Vector2(9999, 9999)
  container.style.touchAction = 'none'
  container.addEventListener('pointermove', e => {
    const rect = container.getBoundingClientRect()
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  })
  container.addEventListener('pointerleave', () => { mouse.x = 9999; mouse.y = 9999 })

  // planet particles — fibonacci sphere
  const planetCount = 12000
  const planetPos = new Float32Array(planetCount * 3)
  const planetBase = new Float32Array(planetCount * 3)
  const planetPhase = new Float32Array(planetCount)
  const golden = Math.PI * (3 - Math.sqrt(5))

  for (let i = 0; i < planetCount; i++) {
    const y = 1 - (i / (planetCount - 1)) * 2
    const radius = Math.sqrt(1 - y * y)
    const theta = golden * i
    const x = Math.cos(theta) * radius
    const z = Math.sin(theta) * radius
    planetBase[i * 3] = x
    planetBase[i * 3 + 1] = y
    planetBase[i * 3 + 2] = z
    planetPos[i * 3] = x
    planetPos[i * 3 + 1] = y
    planetPos[i * 3 + 2] = z
    planetPhase[i] = Math.random() * Math.PI * 2
  }

  const planetGeo = new THREE.BufferGeometry()
  planetGeo.setAttribute('position', new THREE.BufferAttribute(planetPos, 3))
  const planetMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uDiscovering: { value: 0 },
      uMouse: { value: new THREE.Vector3(9999, 9999, 9999) },
    },
    vertexShader: `
      uniform float uTime;
      uniform float uDiscovering;
      uniform vec3 uMouse;
      varying float vBright;
      varying vec3 vPos;
      varying float vFresnel;
      void main() {
        vPos = position;
        vec3 norm = normalize(position);

        // wrap lighting (Valve 2004) — extends diffuse past terminator
        vec3 light = normalize(vec3(0.15, -0.3, 0.9));
        float wrap = 0.3;
        float diffuse = max(0.0, (dot(norm, light) + wrap) / (1.0 + wrap));
        vBright = max(0.1, diffuse);

        // latitude band modulation
        vBright *= 0.85 + 0.15 * sin(norm.y * 22.0 + uTime * 0.5);

        // Fresnel rim glow (Schlick approximation)
        vec3 viewDir = normalize(cameraPosition - (modelMatrix * vec4(position, 1.0)).xyz);
        vec3 worldNorm = normalize((modelMatrix * vec4(norm, 0.0)).xyz);
        vFresnel = pow(1.0 - max(dot(worldNorm, viewDir), 0.0), 3.0);

        // GPU-side mouse repulsion
        vec3 worldPos = (modelMatrix * vec4(position, 1.0)).xyz;
        vec3 dir = worldPos - uMouse;
        float dist = length(dir);
        float force = smoothstep(0.6, 0.0, dist) * 0.15;
        vec3 displaced = position + normalize(dir) * force;

        vec4 mv = modelViewMatrix * vec4(displaced, 1.0);
        gl_PointSize = max(2.0, 5.5 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uDiscovering;
      varying float vBright;
      varying vec3 vPos;
      varying float vFresnel;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float glow = 1.0 - d * 2.0;
        glow = glow * glow;

        float pulse = 0.65 + 0.35 * sin(uTime * 1.5);
        vec3 gold = vec3(0.94, 0.71, 0.16) * vBright;
        vec3 green = vec3(0.0, vBright * pulse, vBright * 0.14);
        vec3 col = mix(gold, green, uDiscovering);

        // add fresnel rim
        vec3 rimColor = mix(vec3(0.7, 0.5, 0.15), vec3(0.0, 0.8, 0.2), uDiscovering);
        col += rimColor * vFresnel * 0.6;

        col += col * glow * 0.4;
        gl_FragColor = vec4(col, 0.7 + glow * 0.3);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  })
  const planet = new THREE.Points(planetGeo, planetMat)
  scene.add(planet)

  // ring particles
  const ringCount = 8000
  const ringPos = new Float32Array(ringCount * 3)
  const ringBase = new Float32Array(ringCount * 3)
  const ringRadius = new Float32Array(ringCount)
  const ringPhase = new Float32Array(ringCount)
  const ringIn = 1.4, ringOut = 2.3

  for (let i = 0; i < ringCount; i++) {
    const angle = Math.random() * Math.PI * 2
    const r = ringIn + Math.random() * (ringOut - ringIn)
    const gap = 1.75
    if (Math.abs(r - gap) < 0.06) {
      ringBase[i * 3] = 0
      ringBase[i * 3 + 1] = 0
      ringBase[i * 3 + 2] = 0
      ringRadius[i] = 0
    } else {
      ringBase[i * 3] = Math.cos(angle) * r
      ringBase[i * 3 + 1] = (Math.random() - 0.5) * 0.03
      ringBase[i * 3 + 2] = Math.sin(angle) * r
      ringRadius[i] = r
    }
    ringPos[i * 3] = ringBase[i * 3]
    ringPos[i * 3 + 1] = ringBase[i * 3 + 1]
    ringPos[i * 3 + 2] = ringBase[i * 3 + 2]
    ringPhase[i] = Math.random() * Math.PI * 2
  }

  const ringGeo = new THREE.BufferGeometry()
  ringGeo.setAttribute('position', new THREE.BufferAttribute(ringPos, 3))
  const ringMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uDiscovering: { value: 0 },
      uMouse: { value: new THREE.Vector3(9999, 9999, 9999) },
      uLight: { value: new THREE.Vector3(0.15, -0.3, 0.9).normalize() },
    },
    vertexShader: `
      uniform float uTime;
      uniform vec3 uMouse;
      varying float vDist;
      varying float vBright;
      varying vec3 vWorldPos;
      void main() {
        vDist = length(position.xz);
        float t = (vDist - 1.4) / 0.9;
        vBright = 0.15 + 0.6 * (1.0 - t);

        // density wave modulation (Lin & Shu 1964 approximation)
        vBright *= 0.88 + 0.12 * sin(vDist * 14.0 + uTime * 0.3);

        vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;

        // GPU-side mouse repulsion
        vec3 dir = vWorldPos - uMouse;
        float dist = length(dir);
        float force = smoothstep(0.8, 0.0, dist) * 0.12;
        vec3 displaced = position + normalize(dir) * force;

        vec4 mv = modelViewMatrix * vec4(displaced, 1.0);
        gl_PointSize = max(1.5, 4.0 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uDiscovering;
      uniform vec3 uLight;
      varying float vBright;
      varying float vDist;
      varying vec3 vWorldPos;

      // Henyey-Greenstein phase function for forward scattering
      float HG(float cosTheta, float g) {
        float g2 = g * g;
        return (1.0 - g2) / (4.0 * 3.14159 * pow(1.0 + g2 - 2.0 * g * cosTheta, 1.5));
      }

      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float glow = 1.0 - d * 2.0;
        glow = glow * glow;

        // forward scattering — rings brighter when backlit
        vec3 viewDir = normalize(cameraPosition - vWorldPos);
        float cosTheta = dot(viewDir, uLight);
        float scatter = HG(cosTheta, 0.35);
        float scatterBoost = 0.6 + scatter * 1.5;

        float pulse = 0.65 + 0.35 * sin(uTime * 1.5);
        vec3 gold = vec3(0.85, 0.65, 0.25) * vBright * scatterBoost;
        vec3 green = vec3(0.0, vBright * pulse * scatterBoost, vBright * 0.1);
        vec3 col = mix(gold, green, uDiscovering);
        col += col * glow * 0.3;
        gl_FragColor = vec4(col, 0.6 + glow * 0.3);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  })
  const rings = new THREE.Points(ringGeo, ringMat)
  rings.rotation.x = 0.35
  scene.add(rings)

  planet.rotation.x = 0.35

  // stars
  const starCount = 500
  const starPos = new Float32Array(starCount * 3)
  const starPhases = new Float32Array(starCount)
  for (let i = 0; i < starCount; i++) {
    starPos[i * 3] = (Math.random() - 0.5) * 30
    starPos[i * 3 + 1] = (Math.random() - 0.5) * 30
    starPos[i * 3 + 2] = -10 - Math.random() * 20
    starPhases[i] = Math.random() * Math.PI * 2
  }
  const starGeo = new THREE.BufferGeometry()
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
  starGeo.setAttribute('aPhase', new THREE.BufferAttribute(starPhases, 1))
  const starMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uDiscovering: { value: 0 } },
    vertexShader: `
      attribute float aPhase;
      varying float vPhase;
      void main() {
        vPhase = aPhase;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.0, 2.5 * (1.0 / -mv.z));
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uDiscovering;
      varying float vPhase;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        float twinkle = 0.3 + 0.7 * abs(sin(uTime * 0.5 + vPhase));
        vec3 white = vec3(twinkle);
        vec3 green = vec3(0.0, twinkle, 0.0);
        gl_FragColor = vec4(mix(white, green, uDiscovering), 1.0);
      }
    `,
    transparent: true,
    depthWrite: false
  })
  scene.add(new THREE.Points(starGeo, starMat))

  // moon sprites for discovered services
  const moonGroup = new THREE.Group()
  moonGroup.rotation.x = 0.45
  scene.add(moonGroup)

  // label as HTML overlay
  const label = document.createElement('div')
  label.textContent = 'S A T U R N'
  label.style.cssText = 'position:absolute;bottom:8%;left:0;right:0;text-align:center;color:#fff;font:1.2em monospace;letter-spacing:0.4em;pointer-events:none;text-shadow:0 0 10px rgba(255,200,60,0.5)'
  container.appendChild(label)

  let discovering = false
  let discoverLerp = 0
  const clock = new THREE.Clock()

  // raycaster for mouse → world projection
  const raycaster = new THREE.Raycaster()

  function animate() {
    const t = clock.getElapsedTime()

    // smooth discovering transition
    discoverLerp += ((discovering ? 1 : 0) - discoverLerp) * 0.04

    // rotate — planet spins, rings drift slowly
    planet.rotation.y = t * 0.12
    rings.rotation.y = t * 0.05

    // project mouse into world space for GPU repulsion
    raycaster.setFromCamera(mouse, camera)
    const mouseWorld = new THREE.Vector3()
    raycaster.ray.at(camera.position.z, mouseWorld)
    planetMat.uniforms.uMouse.value.copy(mouseWorld)
    ringMat.uniforms.uMouse.value.copy(mouseWorld)

    // update planet particles — breathing
    const pPos = planetGeo.attributes.position.array
    for (let i = 0; i < planetCount; i++) {
      const i3 = i * 3
      const bx = planetBase[i3], by = planetBase[i3 + 1], bz = planetBase[i3 + 2]
      const breathe = 1 + 0.008 * Math.sin(t * 2 + planetPhase[i])
      pPos[i3] = bx * breathe
      pPos[i3 + 1] = by * breathe
      pPos[i3 + 2] = bz * breathe
    }
    planetGeo.attributes.position.needsUpdate = true

    // update ring particles — Keplerian differential rotation (v ∝ 1/√r)
    const rPos = ringGeo.attributes.position.array
    for (let i = 0; i < ringCount; i++) {
      const i3 = i * 3
      const r = ringRadius[i]
      if (r === 0) continue
      const speed = 0.04 / Math.sqrt(r)
      const angle = Math.atan2(ringBase[i3 + 2], ringBase[i3]) + t * speed + ringPhase[i] * 0.001
      rPos[i3] = Math.cos(angle) * r
      rPos[i3 + 1] = ringBase[i3 + 1] + Math.sin(t * 1.5 + ringPhase[i]) * 0.01
      rPos[i3 + 2] = Math.sin(angle) * r
    }
    ringGeo.attributes.position.needsUpdate = true

    // update moons
    while (moonGroup.children.length > window.saturnMoons.length) {
      moonGroup.remove(moonGroup.children[moonGroup.children.length - 1])
    }
    window.saturnMoons.forEach((moon, i) => {
      let sprite = moonGroup.children[i]
      if (!sprite) {
        const sg = new THREE.SphereGeometry(0.06, 8, 8)
        const sm = new THREE.MeshBasicMaterial({ color: 0x888888 })
        sprite = new THREE.Mesh(sg, sm)
        moonGroup.add(sprite)
      }
      const speed = 0.3 + i * 0.12
      const orbitR = 1.6 + i * 0.25
      const angle = t * speed + i * Math.PI * 2 / Math.max(window.saturnMoons.length, 1)
      sprite.position.set(
        Math.cos(angle) * orbitR,
        Math.sin(angle) * orbitR * 0.15,
        Math.sin(angle) * orbitR * 0.5
      )
      sprite.material.color.setHex(moon.selected ? 0x00ff00 : 0x888888)
    })

    // uniforms
    planetMat.uniforms.uTime.value = t
    planetMat.uniforms.uDiscovering.value = discoverLerp
    ringMat.uniforms.uTime.value = t
    ringMat.uniforms.uDiscovering.value = discoverLerp
    starMat.uniforms.uTime.value = t
    starMat.uniforms.uDiscovering.value = discoverLerp
    filmPass.uniforms.uTime.value = t

    // label glow in discover mode
    if (discoverLerp > 0.01) {
      label.style.color = `rgb(${Math.round(255 * (1 - discoverLerp))},255,${Math.round(255 * (1 - discoverLerp))})`
      label.style.textShadow = `0 0 12px rgba(0,255,0,${discoverLerp * 0.6})`
    } else {
      label.style.color = '#fff'
      label.style.textShadow = '0 0 8px rgba(255,200,60,0.4)'
    }

    composer.render()
    requestAnimationFrame(animate)
  }

  animate()

  // resize handler
  const ro = new ResizeObserver(() => {
    const w = container.clientWidth, h = container.clientHeight
    if (w === 0 || h === 0) return
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    composer.setSize(w, h)
  })
  ro.observe(container)

  window.saturnDiscover = (on) => { discovering = on }
}

// ===== BRUTUS 3D BUST =====
function initBrutus() {
  const container = document.getElementById('brutus-container')
  if (!container) return
  container.innerHTML = ''
  const w = container.clientWidth, h = container.clientHeight
  if (w === 0 || h === 0) return

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 100)
  camera.position.set(0, 0.3, 5.5)
  camera.lookAt(0, 0.2, 0)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 1)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)

  // post-processing — same chain as Saturn
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  const clampPass = new ShaderPass(BrightnessClampShader)
  composer.addPass(clampPass)
  const bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 0.8, 0.3, 0.85)
  composer.addPass(bloom)
  const chromaPass = new ShaderPass(ChromaticAberrationShader)
  composer.addPass(chromaPass)
  const filmPass = new ShaderPass(FilmGrainShader)
  composer.addPass(filmPass)
  composer.addPass(new OutputPass())

  // pointer tracking
  const mouse = new THREE.Vector2(9999, 9999)
  container.style.touchAction = 'none'
  container.addEventListener('pointermove', e => {
    const rect = container.getBoundingClientRect()
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  })
  container.addEventListener('pointerleave', () => { mouse.x = 9999; mouse.y = 9999 })

  // --- bust geometry from radial profile slices ---
  // Each slice: [y, frontRadius, backRadius, xOffset]
  // y goes from bottom (-1.8) to top (1.8)
  // radii define the bust cross-section at that height
  const profile = [
    // base / pedestal
    [-1.80, 0.90, 0.50, 0.00],
    [-1.70, 0.88, 0.48, 0.00],
    [-1.60, 0.85, 0.46, 0.00],
    [-1.50, 0.80, 0.44, 0.00],
    // chest / shoulders
    [-1.30, 0.78, 0.50, 0.00],
    [-1.10, 0.82, 0.55, 0.00],
    [-0.90, 0.90, 0.58, 0.00],
    [-0.70, 0.95, 0.60, 0.00],
    [-0.50, 0.92, 0.58, 0.00],
    [-0.30, 0.80, 0.52, 0.00],
    // neck
    [-0.10, 0.38, 0.35, 0.00],
    [ 0.00, 0.35, 0.33, 0.00],
    [ 0.10, 0.33, 0.32, 0.00],
    // chin / jaw
    [ 0.20, 0.36, 0.34, 0.02],
    [ 0.30, 0.42, 0.38, 0.03],
    [ 0.40, 0.48, 0.42, 0.04],
    // face
    [ 0.50, 0.52, 0.46, 0.04],
    [ 0.60, 0.54, 0.50, 0.03],
    [ 0.70, 0.55, 0.52, 0.02],
    [ 0.80, 0.54, 0.54, 0.01],
    [ 0.90, 0.52, 0.54, 0.00],
    // brow / forehead
    [ 1.00, 0.50, 0.52, -0.02],
    [ 1.10, 0.48, 0.50, -0.03],
    [ 1.20, 0.46, 0.50, -0.04],
    // top of head
    [ 1.30, 0.44, 0.48, -0.04],
    [ 1.40, 0.40, 0.44, -0.03],
    [ 1.50, 0.34, 0.38, -0.02],
    [ 1.60, 0.26, 0.30, -0.01],
    [ 1.70, 0.16, 0.20, 0.00],
    [ 1.80, 0.06, 0.08, 0.00],
  ]

  // nose ridge — extra points protruding forward
  const noseProfile = [
    [0.35, 0.18], // [y, protrusion from front]
    [0.45, 0.22],
    [0.55, 0.25],
    [0.65, 0.26],
    [0.75, 0.24],
    [0.85, 0.20],
    [0.95, 0.12],
  ]

  // eye sockets — indentations
  const eyeY = 0.75, eyeSpread = 0.22, eyeDepth = 0.06

  const bustCount = 10000
  const bustPos = new Float32Array(bustCount * 3)
  const bustBase = new Float32Array(bustCount * 3)
  const bustPhase = new Float32Array(bustCount)
  const bustNormals = new Float32Array(bustCount * 3)
  let idx = 0

  // helper: interpolate profile at arbitrary y
  function sampleProfile(y) {
    if (y <= profile[0][0]) return profile[0]
    if (y >= profile[profile.length - 1][0]) return profile[profile.length - 1]
    for (let i = 0; i < profile.length - 1; i++) {
      if (y >= profile[i][0] && y <= profile[i + 1][0]) {
        const t = (y - profile[i][0]) / (profile[i + 1][0] - profile[i][0])
        return [
          y,
          profile[i][1] + (profile[i + 1][1] - profile[i][1]) * t,
          profile[i][2] + (profile[i + 1][2] - profile[i][2]) * t,
          profile[i][3] + (profile[i + 1][3] - profile[i][3]) * t,
        ]
      }
    }
    return profile[0]
  }

  // helper: nose protrusion at y
  function noseBump(y) {
    if (y < noseProfile[0][0] || y > noseProfile[noseProfile.length - 1][0]) return 0
    for (let i = 0; i < noseProfile.length - 1; i++) {
      if (y >= noseProfile[i][0] && y <= noseProfile[i + 1][0]) {
        const t = (y - noseProfile[i][0]) / (noseProfile[i + 1][0] - noseProfile[i][0])
        return noseProfile[i][1] + (noseProfile[i + 1][1] - noseProfile[i][1]) * t
      }
    }
    return 0
  }

  // distribute particles across bust surface
  for (let i = 0; i < bustCount; i++) {
    const y = -1.80 + Math.random() * 3.60
    const [, frontR, backR, xOff] = sampleProfile(y)

    // angle around the vertical axis
    const theta = Math.random() * Math.PI * 2

    // radius varies front-to-back
    const isFront = Math.cos(theta) > 0
    const baseR = isFront ? frontR : backR

    // add some surface noise
    const noise = 1.0 + (Math.random() - 0.5) * 0.08
    let r = baseR * noise

    // nose protrusion (only for forward-facing particles near center)
    const noseR = noseBump(y)
    if (noseR > 0 && Math.abs(theta) < 0.4 && isFront) {
      r += noseR * Math.cos(theta) * (1.0 - Math.abs(theta) / 0.4) * 0.5
    }

    // eye socket indentation
    if (Math.abs(y - eyeY) < 0.08 && isFront) {
      const xPos = Math.sin(theta) * r
      if (Math.abs(Math.abs(xPos) - eyeSpread) < 0.08) {
        r -= eyeDepth
      }
    }

    const x = Math.sin(theta) * r + xOff
    const z = Math.cos(theta) * r

    bustPos[idx * 3] = x
    bustPos[idx * 3 + 1] = y
    bustPos[idx * 3 + 2] = z
    bustBase[idx * 3] = x
    bustBase[idx * 3 + 1] = y
    bustBase[idx * 3 + 2] = z
    bustPhase[idx] = Math.random() * Math.PI * 2

    // approximate normal (radial outward)
    const nx = Math.sin(theta)
    const nz = Math.cos(theta)
    const len = Math.sqrt(nx * nx + nz * nz) || 1
    bustNormals[idx * 3] = nx / len
    bustNormals[idx * 3 + 1] = 0
    bustNormals[idx * 3 + 2] = nz / len

    idx++
  }

  const bustGeo = new THREE.BufferGeometry()
  bustGeo.setAttribute('position', new THREE.BufferAttribute(bustPos, 3))
  bustGeo.setAttribute('aBase', new THREE.BufferAttribute(bustBase, 3))
  bustGeo.setAttribute('aPhase', new THREE.BufferAttribute(bustPhase, 1))
  bustGeo.setAttribute('aNormal', new THREE.BufferAttribute(bustNormals, 3))

  const bustMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector3(9999, 9999, 9999) },
      uActive: { value: 0 },
    },
    vertexShader: `
      attribute vec3 aBase;
      attribute float aPhase;
      attribute vec3 aNormal;
      uniform float uTime;
      uniform vec3 uMouse;
      uniform float uActive;
      varying float vLight;
      varying float vFresnel;
      varying float vY;

      void main() {
        // slow breathing
        float breathe = 1.0 + 0.004 * sin(uTime * 1.5 + aPhase);
        vec3 pos = aBase * breathe;

        // mouse repulsion
        vec3 dir = pos - uMouse;
        float dist = length(dir);
        float force = smoothstep(0.6, 0.0, dist) * 0.2;
        pos += normalize(dir + 0.001) * force;

        vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPos;

        // size — slightly larger than Saturn particles
        gl_PointSize = (2.5 + uActive * 0.5) * (300.0 / -mvPos.z);

        // wrap lighting (light from upper-right-front)
        vec3 lightDir = normalize(vec3(0.5, 0.8, 1.0));
        float wrap = 0.4;
        float NdL = dot(aNormal, lightDir);
        vLight = (NdL + wrap) / (1.0 + wrap);
        vLight = clamp(vLight, 0.15, 1.0);

        // Fresnel rim
        vec3 viewDir = normalize(-mvPos.xyz);
        vFresnel = pow(1.0 - max(dot(aNormal, viewDir), 0.0), 3.0);

        vY = aBase.y;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uActive;
      varying float vLight;
      varying float vFresnel;
      varying float vY;

      void main() {
        // circular point
        vec2 c = gl_PointCoord - 0.5;
        if (dot(c, c) > 0.25) discard;

        // marble-white base with warm shadows
        vec3 baseColor = vec3(0.85, 0.82, 0.78);
        vec3 shadowColor = vec3(0.3, 0.28, 0.25);
        vec3 color = mix(shadowColor, baseColor, vLight);

        // Fresnel rim — cool blue-white edge glow
        vec3 rimColor = vec3(0.6, 0.7, 0.9);
        color += rimColor * vFresnel * 0.4;

        // active state — subtle warm glow (when Brutus is routing)
        vec3 activeColor = vec3(1.0, 0.85, 0.5);
        color = mix(color, activeColor, uActive * 0.3 * (0.5 + 0.5 * vFresnel));

        // soft alpha for depth
        float alpha = 0.55 + 0.25 * vLight;

        gl_FragColor = vec4(color, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
  })

  const bust = new THREE.Points(bustGeo, bustMat)
  bust.rotation.x = -0.1
  scene.add(bust)

  // background stars (fewer than Saturn)
  const starCount = 300
  const starPos = new Float32Array(starCount * 3)
  const starPhase = new Float32Array(starCount)
  for (let i = 0; i < starCount; i++) {
    starPos[i * 3] = (Math.random() - 0.5) * 30
    starPos[i * 3 + 1] = (Math.random() - 0.5) * 30
    starPos[i * 3 + 2] = -(10 + Math.random() * 20)
    starPhase[i] = Math.random() * Math.PI * 2
  }
  const starGeo = new THREE.BufferGeometry()
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
  starGeo.setAttribute('aPhase', new THREE.BufferAttribute(starPhase, 1))

  const starMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      attribute float aPhase;
      uniform float uTime;
      varying float vTwinkle;
      void main() {
        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPos;
        gl_PointSize = 1.5 * (300.0 / -mvPos.z);
        vTwinkle = 0.5 + 0.5 * sin(uTime * 2.0 + aPhase);
      }
    `,
    fragmentShader: `
      varying float vTwinkle;
      void main() {
        vec2 c = gl_PointCoord - 0.5;
        if (dot(c, c) > 0.25) discard;
        gl_FragColor = vec4(vec3(0.6, 0.6, 0.7) * vTwinkle, vTwinkle * 0.6);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  })
  scene.add(new THREE.Points(starGeo, starMat))

  // label
  const label = document.createElement('div')
  label.textContent = 'B R U T U S'
  label.style.cssText = 'position:absolute;bottom:8%;left:0;right:0;text-align:center;color:#d4c9b8;font:1.2em monospace;letter-spacing:0.4em;pointer-events:none;text-shadow:0 0 10px rgba(180,160,120,0.5)'
  container.appendChild(label)

  let active = false
  let activeLerp = 0
  const clock = new THREE.Clock()
  const raycaster = new THREE.Raycaster()

  function animate() {
    const t = clock.getElapsedTime()

    activeLerp += ((active ? 1 : 0) - activeLerp) * 0.04

    // slow rotation
    bust.rotation.y = Math.sin(t * 0.15) * 0.25

    // project mouse into world space
    raycaster.setFromCamera(mouse, camera)
    const mouseWorld = new THREE.Vector3()
    raycaster.ray.at(camera.position.z, mouseWorld)
    bustMat.uniforms.uMouse.value.copy(mouseWorld)

    // breathing update
    const bPos = bustGeo.attributes.position.array
    for (let i = 0; i < bustCount; i++) {
      const i3 = i * 3
      const breathe = 1 + 0.004 * Math.sin(t * 1.5 + bustPhase[i])
      bPos[i3] = bustBase[i3] * breathe
      bPos[i3 + 1] = bustBase[i3 + 1] * breathe
      bPos[i3 + 2] = bustBase[i3 + 2] * breathe
    }
    bustGeo.attributes.position.needsUpdate = true

    bustMat.uniforms.uTime.value = t
    bustMat.uniforms.uActive.value = activeLerp
    starMat.uniforms.uTime.value = t
    filmPass.uniforms.uTime.value = t

    // label glow in active mode
    if (activeLerp > 0.01) {
      const g = Math.round(160 + 95 * activeLerp)
      label.style.color = `rgb(255,${g},${Math.round(80 + 100 * (1 - activeLerp))})`
      label.style.textShadow = `0 0 12px rgba(255,200,80,${activeLerp * 0.6})`
    } else {
      label.style.color = '#d4c9b8'
      label.style.textShadow = '0 0 8px rgba(180,160,120,0.4)'
    }

    composer.render()
    requestAnimationFrame(animate)
  }

  animate()

  const ro = new ResizeObserver(() => {
    const w = container.clientWidth, h = container.clientHeight
    if (w === 0 || h === 0) return
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    composer.setSize(w, h)
  })
  ro.observe(container)

  window.brutusActive = (on) => { active = on }
}

let _brutusInited = false
function ensureBrutus() {
  if (_brutusInited) return
  const c = document.getElementById('brutus-container')
  if (!c || c.clientWidth === 0) return
  _brutusInited = true
  initBrutus()
}

window.addEventListener('load', () => {
  setTimeout(initSaturn, 100)
  setTimeout(initWelcomeSaturn, 200)
})

// ===== DISCOVER =====
let discoveredServices = []

function render(list, items, type) {
  list.innerHTML = ''
  items.forEach((s, i) => {
    const div = document.createElement('div')
    div.className = 'checklist-item'
    div.style.setProperty('--i', i)
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
  services.forEach((s, i) => {
    const div = document.createElement('div')
    div.className = 'checklist-item'
    div.style.setProperty('--i', i)
    const tag = s.builtin ? '<span class="status-badge status-unknown">BUILT-IN</span>' : ''
    const info = s.port && s.running ? `<span class="status-badge" style="color:var(--muted)">:${s.port}</span>` : ''
    div.innerHTML = `
      <span class="name">${s.name}</span>
      <span class="status-badge" style="color:var(--muted)">${s.deployment} / ${s.api_type}</span>
      <span class="status-badge" style="color:var(--muted)">p${s.priority}</span>
      ${tag}
      ${info}
      ${statusBadge(s)}
      <button class="btn btn-secondary btn-cfg" data-name="${s.name}" title="Settings">&#9881;</button>
      ${actionBtn(s)}
    `
    // wire config button
    div.querySelector('.btn-cfg').addEventListener('click', (e) => {
      e.stopPropagation()
      openConfig(s.name)
    })
    // wire start/stop buttons
    const btn = div.querySelector('.btn-start, .btn-stop')
    if (btn) {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation()
        btn.disabled = true
        btn.textContent = s.running ? 'Stopping...' : 'Starting...'
        const starting = !s.running
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
        if (starting) discoverBtn.click()
      })
    }
    list.appendChild(div)
  })
}

loadServices()

// admin password gate for service configuration
let adminUnlocked = sessionStorage.getItem('saturn-admin') === '1'

function showAdminState() {
  document.getElementById('admin-gate').classList.toggle('hidden', adminUnlocked)
  document.getElementById('admin-section').classList.toggle('hidden', !adminUnlocked)
}
showAdminState()

async function tryAdminAuth() {
  const pw = document.getElementById('admin-pw').value
  if (!pw) return
  try {
    const res = await fetch('/api/admin/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    })
    if (res.ok) {
      adminUnlocked = true
      sessionStorage.setItem('saturn-admin', '1')
      showAdminState()
    } else {
      toast('Wrong password')
      document.getElementById('admin-pw').value = ''
    }
  } catch {
    toast('Auth failed')
  }
}

document.getElementById('admin-pw-submit').addEventListener('click', tryAdminAuth)
document.getElementById('admin-pw').addEventListener('keydown', e => {
  if (e.key === 'Enter') tryAdminAuth()
})

document.getElementById('config-btn').addEventListener('click', () => {
  document.getElementById('discover-main').classList.add('hidden')
  document.getElementById('config-page').classList.remove('hidden')
  initConfigStars()
})

document.getElementById('cfg-back').addEventListener('click', () => {
  document.getElementById('config-page').classList.add('hidden')
  document.getElementById('discover-main').classList.remove('hidden')
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
  document.getElementById('discover-main').classList.remove('hidden')
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
    // constellation lines
    const linkDist = 100
    for (let i = 0; i < stars.length; i++) {
      for (let j = i + 1; j < stars.length; j++) {
        const dx = stars[i].x - stars[j].x
        const dy = stars[i].y - stars[j].y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < linkDist) {
          ctx.strokeStyle = `rgba(255,255,255,${(1 - d / linkDist) * 0.15})`
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(stars[i].x, stars[i].y)
          ctx.lineTo(stars[j].x, stars[j].y)
          ctx.stroke()
        }
      }
    }
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

// localStorage persistence
const STORAGE_KEY = 'saturn-chats'
const PREFS_KEY = 'saturn-prefs'
const MAX_CHATS = 50

function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.slice(0, MAX_CHATS)
  } catch { /* corrupt data */ }
  return []
}

function saveChats() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats.slice(0, MAX_CHATS)))
  } catch { /* quota exceeded — drop oldest */
    while (chats.length > 10) {
      chats.pop()
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(chats)); return } catch { /* keep trimming */ }
    }
  }
}

function loadPrefs() {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {}
}

function savePrefs(updates) {
  const prefs = loadPrefs()
  Object.assign(prefs, updates)
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)) } catch { /* ignore */ }
}

const chats = loadChats()
let activeChat = chats.length > 0 ? 0 : null
let sending = false
let streamState = 'idle'
let activeController = null

const TOKEN_BUDGET = 100000
function estimate(text) {
  return Math.ceil((text || '').length / 4)
}

function compact(msgs) {
  const total = msgs.reduce((s, m) => s + estimate(m.content), 0)
  if (total <= TOKEN_BUDGET) return msgs
  const keep = 4
  const head = msgs[0]?.role === 'system' ? [msgs[0]] : []
  const tail = msgs.slice(-keep)
  let rest = msgs.slice(head.length, -keep)
  // drop oldest until under budget or rest is empty
  while (rest.length > 0) {
    const cur = head.reduce((s, m) => s + estimate(m.content), 0)
      + estimate('[Earlier messages trimmed to fit context window]')
      + rest.reduce((s, m) => s + estimate(m.content), 0)
      + tail.reduce((s, m) => s + estimate(m.content), 0)
    if (cur <= TOKEN_BUDGET) break
    rest.shift()
  }
  const trimmed = msgs.length - head.length - rest.length - keep
  if (trimmed <= 0) return msgs
  toast(`Trimmed ${trimmed} old messages to fit context`)
  // insert inline notification in chat thread
  if (activeChat !== null) {
    const notice = document.createElement('div')
    notice.className = 'msg system-notice'
    notice.textContent = `⚠ Trimmed ${trimmed} earlier messages to fit context window`
    messagesEl.appendChild(notice)
    messagesEl.scrollTop = messagesEl.scrollHeight
  }
  return [...head, { role: 'system', content: '[Earlier messages trimmed to fit context window]' }, ...rest, ...tail]
}

function updateContextIndicator() {
  const el = document.getElementById('context-indicator')
  if (activeChat === null || chats[activeChat].messages.length === 0) {
    el.classList.remove('visible', 'warn', 'critical')
    return
  }
  const total = chats[activeChat].messages.reduce((s, m) => s + estimate(m.text), 0)
  const k = (total / 1000).toFixed(total < 1000 ? 1 : 0)
  const budgetK = (TOKEN_BUDGET / 1000).toFixed(0)
  el.textContent = `~${k}K / ${budgetK}K tokens`
  el.classList.add('visible')
  el.classList.toggle('warn', total > TOKEN_BUDGET * 0.7)
  el.classList.toggle('critical', total > TOKEN_BUDGET * 0.9)
}

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// markdown rendering for assistant messages
;(function() {
  if (typeof marked !== 'undefined') {
    marked.use({ gfm: true, breaks: true })
  }
})()

function renderMarkdown(s) {
  if (typeof marked === 'undefined') return esc(s)
  const raw = marked.parse(s)
  if (typeof DOMPurify !== 'undefined') return DOMPurify.sanitize(raw)
  return raw
}

function highlightCode(el) {
  if (typeof hljs === 'undefined') return
  el.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block))
}

function splitThinking(text) {
  const open = text.indexOf('<think>')
  if (open === -1) return { thinking: '', body: text, pending: false }
  const close = text.indexOf('</think>', open)
  if (close === -1) return { thinking: text.slice(open + 7), body: '', pending: true }
  return {
    thinking: text.slice(open + 7, close),
    body: text.slice(0, open) + text.slice(close + 8),
    pending: false,
  }
}

function renderThinkingHTML(thinking) {
  if (!thinking) return ''
  return `<details class="thinking-block"><summary class="thinking-toggle">Thinking\u2026 (click to expand)</summary><div class="thinking-content">${renderMarkdown(thinking)}</div></details>`
}

function renderWithThinking(text) {
  const { thinking, body, pending } = splitThinking(text)
  if (pending) return renderThinkingHTML(thinking) + '<span class="cursor">▊</span>'
  return renderThinkingHTML(thinking) + renderMarkdown(body || '[empty response]')
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
  // Brutus auto-routing option
  const sep = document.createElement('option')
  sep.disabled = true
  sep.textContent = '────────────'
  serviceSelect.appendChild(sep)
  const brutusOpt = document.createElement('option')
  brutusOpt.value = '__brutus__'
  brutusOpt.textContent = '⊛ Brutus (auto)'
  serviceSelect.appendChild(brutusOpt)
  // restore previous selection or saved pref
  const saved = prev || loadPrefs().service
  if (saved && [...serviceSelect.options].some(o => o.value === saved)) {
    serviceSelect.value = saved
  }
  // apply deferred brutus selection from hash deep-link
  if (_pendingBrutus) {
    serviceSelect.value = '__brutus__'
    _pendingBrutus = false
  }
  loadModels()
}
let _pendingBrutus = false

// fetch models from selected service
async function loadModels() {
  const name = serviceSelect.value
  if (!name) {
    modelSelect.innerHTML = '<option value="" disabled selected>-- select service --</option>'
    return
  }
  if (name === '__brutus__') {
    modelSelect.innerHTML = '<option value="auto" selected>auto (best available)</option>'
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
    const savedModel = loadPrefs().model
    if (savedModel && [...modelSelect.options].some(o => o.value === savedModel)) {
      modelSelect.value = savedModel
    }
  } catch {
    modelSelect.innerHTML = '<option value="" disabled selected>-- error --</option>'
  }
}

serviceSelect.addEventListener('change', () => {
  savePrefs({ service: serviceSelect.value })
  loadModels()
})
modelSelect.addEventListener('change', () => {
  savePrefs({ model: modelSelect.value })
})

// ===== MODEL AGGREGATION =====
const modelsPanel = document.getElementById('models-panel')
const modelList = document.getElementById('model-list')
let allModels = []

// models panel is accessed via tools panel only

document.getElementById('models-refresh').addEventListener('click', refreshAllModels)

async function refreshAllModels() {
  modelList.innerHTML = '<div class="model-item"><span class="model-name" style="color:var(--muted)">Loading...</span></div>'
  try {
    const res = await fetch('/api/models/all')
    allModels = await res.json()
  } catch {
    allModels = []
  }
  renderModelList()
}

function renderModelList() {
  modelList.innerHTML = ''
  if (allModels.length === 0) {
    modelList.innerHTML = '<div class="model-item"><span class="model-name" style="color:var(--muted)">No models found — run Discover first</span></div>'
    return
  }
  allModels.forEach(m => {
    const div = document.createElement('div')
    div.className = 'model-item'
    div.dataset.model = m.id
    div.dataset.service = m.service
    div.innerHTML = `<span class="status-dot"></span><span class="model-name">${esc(m.id)}</span><span class="model-service">${esc(m.service)}</span>`
    div.addEventListener('click', () => selectModel(m.service, m.id))
    modelList.appendChild(div)
  })
}

function selectModel(svc, mid) {
  // set service dropdown
  if ([...serviceSelect.options].some(o => o.value === svc)) {
    serviceSelect.value = svc
    savePrefs({ service: svc })
  }
  // load models for that service, then select the model
  loadModels().then(() => {
    if ([...modelSelect.options].some(o => o.value === mid)) {
      modelSelect.value = mid
      savePrefs({ model: mid })
    }
  })
  modelsPanel.classList.add('hidden')
}

// auto-refresh models every 30s (same pattern as omlx-saturn chat.html)
setInterval(() => {
  if (serviceSelect.value) loadModels()
}, 30000)

function renderMessages() {
  messagesEl.querySelectorAll('.msg').forEach(m => m.remove())
  messagesEl.querySelectorAll('.regen-row').forEach(m => m.remove())
  if (activeChat === null || chats[activeChat].messages.length === 0) {
    welcome.classList.remove('hidden')
    updateContextIndicator()
    return
  }
  welcome.classList.add('hidden')
  const msgs = chats[activeChat].messages
  msgs.forEach((m, i) => {
    const div = document.createElement('div')
    if (m.role === 'user') {
      div.className = 'msg user'
      div.innerHTML = `<div class="prefix">&gt; you</div><div class="bubble">${esc(m.text)}</div>`
    } else {
      div.className = 'msg assistant'
      const toolHTML = renderToolsInline(m.toolCalls, m.toolResults)
      const metaLabel = m.routedBy === 'brutus'
        ? `brutus → ${m.service || ''} // ${m.model || ''}`
        : `${m.service || ''} // ${m.model || ''}`
      div.innerHTML = `
        <div class="meta">${metaLabel}</div>
        <div class="bubble markdown-body">${toolHTML}${renderWithThinking(m.text)}</div>
      `
    }
    messagesEl.appendChild(div)

    // regenerate button on last assistant message
    if (m.role === 'assistant' && i === msgs.length - 1 && !sending) {
      const row = document.createElement('div')
      row.className = 'regen-row'
      row.innerHTML = '<button class="btn btn-secondary regen-btn">↻ Regenerate</button>'
      row.querySelector('.regen-btn').addEventListener('click', regenerate)
      messagesEl.appendChild(row)
    }
  })
  highlightCode(messagesEl)
  addCopyButtons(messagesEl)
  messagesEl.scrollTop = messagesEl.scrollHeight
  updateContextIndicator()
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

function regenerate() {
  if (sending || activeChat === null) return
  const chat = chats[activeChat]
  if (chat.messages.length < 2) return
  // find last user message
  let lastUserIdx = -1
  for (let i = chat.messages.length - 1; i >= 0; i--) {
    if (chat.messages[i].role === 'user') { lastUserIdx = i; break }
  }
  if (lastUserIdx === -1) return
  const userText = chat.messages[lastUserIdx].text
  // remove everything after (and including) the last assistant response
  chat.messages.splice(lastUserIdx + 1)
  saveChats()
  renderMessages()
  // re-send
  input.value = userText
  send()
}

function newChat() {
  chats.unshift({ name: 'New Chat', messages: [] })
  if (chats.length > MAX_CHATS) chats.length = MAX_CHATS
  saveChats()
  loadChat(0)
}

// stream chat completions from saturn service — mirrors omlx saturn proxy pattern
async function send() {
  const text = input.value.trim()
  if (!text || sending) return
  input.value = ''
  input.style.height = 'auto'

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

  // prepend file context if attached
  let fullText = text
  if (attachedFile) {
    fullText = `--- File: ${attachedFile.name} ---\n${attachedFile.content}\n---\n${text}`
    clearAttachment()
  }

  chat.messages.push({ role: 'user', text: fullText })
  saveChats()
  welcome.classList.add('hidden')

  const userDiv = document.createElement('div')
  userDiv.className = 'msg user'
  userDiv.innerHTML = `<div class="prefix">&gt; you</div><div class="bubble">${esc(text)}</div>`
  messagesEl.appendChild(userDiv)
  messagesEl.scrollTop = messagesEl.scrollHeight

  // build OpenAI-format messages array
  const sysPrompt = getSystemPrompt()
  const apiMessages = [
    ...(sysPrompt ? [{ role: 'system', content: sysPrompt }] : []),
    ...chat.messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.text }))
  ]
  const compacted = compact(apiMessages)

  const isBrutus = service === '__brutus__'

  // create assistant placeholder with streaming cursor
  const aDiv = document.createElement('div')
  aDiv.className = 'msg assistant'
  aDiv.innerHTML = `
    <div class="meta">${isBrutus ? 'brutus // routing...' : `${esc(service)} // ${esc(model)}`}</div>
    <div class="bubble markdown-body"><span class="cursor">▊</span></div>
  `
  messagesEl.appendChild(aDiv)
  messagesEl.scrollTop = messagesEl.scrollHeight

  const bubble = aDiv.querySelector('.bubble')
  let full = ''
  let toolCalls = []
  sending = true
  sendBtn.textContent = 'Stop'
  sendBtn.classList.add('btn-stop')
  sendBtn.disabled = false

  let actualService = service, actualModel = model

  const endpoint = isBrutus ? '/api/brutus/chat' : '/api/chat'
  const payload = isBrutus
    ? { messages: compacted, ...getActiveParams() }
    : { service, model, messages: compacted, ...getActiveParams() }

  const RETRIES = 3
  const KEEPALIVE = 30000
  let userStopped = false

  for (let attempt = 0; attempt <= RETRIES; attempt++) {
    let controller = new AbortController()
    activeController = controller
    let timer = null

    const resetKeepAlive = () => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        toast('Connection stalled — aborting')
        controller.abort()
      }, KEEPALIVE)
    }

    try {
      if (attempt > 0) {
        streamState = 'reconnecting'
        toast(`Reconnecting (attempt ${attempt}/${RETRIES})...`)
        const base = 1000 * Math.pow(2, attempt - 1)
        await new Promise(r => setTimeout(r, base * (0.75 + Math.random() * 0.5)))
      }

      streamState = 'streaming'

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        const code = res.status

        // retryable HTTP errors — retry if attempts remain
        if ((code === 429 || code >= 500) && attempt < RETRIES) continue

        if (code === 401 || code === 403) {
          full = `[error] Authentication failed — check API key`
          bubble.classList.add('error-permanent')
        } else if (code === 404) {
          full = `[error] Service not found — run Discover`
          bubble.classList.add('error-permanent')
        } else if (code === 429) {
          full = `[error] Rate limited — try again in a moment`
          bubble.classList.add('error-retryable')
        } else if (code >= 500) {
          full = `[error] Server error — the backend may be down`
          bubble.classList.add('error-retryable')
        } else {
          full = `[error] ${err.error || res.statusText}`
          bubble.classList.add('error-permanent')
        }
        bubble.innerHTML = esc(full)
        chat.messages.push({ role: 'assistant', text: full, service: actualService, model: actualModel })
        saveChats()
        streamState = 'error'
        return
      }

      // read Brutus routing metadata from headers
      if (isBrutus) {
        actualService = res.headers.get('X-Brutus-Service') || 'unknown'
        actualModel = res.headers.get('X-Brutus-Model') || 'auto'
        const skipped = res.headers.get('X-Brutus-Skipped')
        const latency = res.headers.get('X-Brutus-Latency')
        const meta = aDiv.querySelector('.meta')
        meta.textContent = `brutus → ${actualService} // ${actualModel}${latency ? ` · ${latency}ms` : ''}`
        if (skipped) {
          const notice = document.createElement('div')
          notice.className = 'msg system-notice'
          notice.textContent = `⚠ skipped: ${skipped} → routed to ${actualService}`
          messagesEl.insertBefore(notice, aDiv)
        }
      }

      // parse SSE stream — same text/event-stream format as omlx
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let stamp = 0
      const THROTTLE = 80

      resetKeepAlive()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        resetKeepAlive()
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') break

          try {
            const chunk = JSON.parse(data)
            const delta = chunk.choices?.[0]?.delta
            if (delta?.content) {
              full += delta.content
              const now = Date.now()
              if (now - stamp < THROTTLE) continue
              stamp = now
              requestAnimationFrame(() => {
                const parts = splitThinking(full)
                if (parts.pending) {
                  bubble.innerHTML = renderThinkingHTML(parts.thinking) + '<span class="cursor">▊</span>'
                } else {
                  bubble.innerHTML = renderThinkingHTML(parts.thinking) + renderMarkdown(parts.body) + '<span class="cursor">▊</span>'
                }
                // phosphor glow on newest content
                const last = bubble.querySelector('p:last-of-type, li:last-of-type, code:last-of-type')
                if (last && !last.classList.contains('token-new')) {
                  last.classList.add('token-new')
                  setTimeout(() => last.classList.remove('token-new'), 600)
                }
                messagesEl.scrollTop = messagesEl.scrollHeight
              })
            }
            if (delta?.tool_calls) {
              for (const tc of delta.tool_calls) {
                const idx = tc.index ?? toolCalls.length
                if (!toolCalls[idx]) toolCalls[idx] = { name: '', arguments: '' }
                if (tc.function?.name) toolCalls[idx].name = tc.function.name
                if (tc.function?.arguments) toolCalls[idx].arguments += tc.function.arguments
              }
              const live = toolCalls.map(tc => {
                let args = {}
                try { args = JSON.parse(tc.arguments) } catch { /* partial */ }
                return renderToolCallInline(tc.name, args, true)
              }).join('')
              const parts = splitThinking(full)
              const body = parts.pending ? '' : renderMarkdown(parts.body)
              bubble.innerHTML = live + renderThinkingHTML(parts.thinking) + body + '<span class="cursor">▊</span>'
              messagesEl.scrollTop = messagesEl.scrollHeight
            }
          } catch {
            // skip malformed chunks
          }
        }
      }

      clearTimeout(timer)

      // execute tool calls with permission gating
      let toolHTML = ''
      let toolResults = []
      if (toolCalls.length > 0) {
        // show pending badges while awaiting permission
        toolHTML = renderToolsInline(toolCalls)
        bubble.innerHTML = toolHTML + renderWithThinking(full)
        messagesEl.scrollTop = messagesEl.scrollHeight

        toolResults = await executeToolCalls(toolCalls, bubble)
        toolHTML = `<div class="tool-calls-row">${renderPermissionBadges(toolCalls, toolResults)}</div>`
      }

      // remove cursor, finalize
      bubble.innerHTML = toolHTML + renderWithThinking(full)
      highlightCode(bubble)
      addCopyButtons(bubble)
      chat.messages.push({
        role: 'assistant', text: full || '[empty response]',
        service: actualService, model: actualModel,
        routedBy: isBrutus ? 'brutus' : undefined,
        toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        toolResults: toolResults.length > 0 ? toolResults : undefined,
      })
      saveChats()
      streamState = 'idle'
      break // success — exit retry loop

    } catch (e) {
      clearTimeout(timer)

      // user-initiated stop — finalize with whatever we have
      if (e.name === 'AbortError' && controller._userStopped) {
        bubble.innerHTML = renderWithThinking(full || '[stopped]')
        highlightCode(bubble)
        addCopyButtons(bubble)
        chat.messages.push({
          role: 'assistant', text: full || '[stopped]',
          service: actualService, model: actualModel,
          routedBy: isBrutus ? 'brutus' : undefined,
        })
        saveChats()
        streamState = 'idle'
        break
      }

      // keepalive abort or network error — retry if attempts remain
      if ((e.name === 'AbortError' || e instanceof TypeError) && attempt < RETRIES) continue

      if (e.name === 'AbortError') {
        full = `[error] Request timed out — no data received for 30s`
        bubble.classList.add('error-network')
      } else if (e instanceof TypeError) {
        full = `[error] Network error — check your connection`
        bubble.classList.add('error-network')
      } else {
        full = `[error] ${e.message}`
        bubble.classList.add('error-retryable')
      }
      bubble.innerHTML = esc(full)
      chat.messages.push({ role: 'assistant', text: full, service: actualService, model: actualModel })
      saveChats()
      streamState = 'error'
    } finally {
      activeController = null
      sending = false
      sendBtn.textContent = 'Send'
      sendBtn.classList.remove('btn-stop')
      sendBtn.disabled = false
    }
  }
  activeController = null
  streamState = streamState === 'streaming' ? 'idle' : streamState
  sending = false
  sendBtn.textContent = 'Send'
  sendBtn.classList.remove('btn-stop')
  sendBtn.disabled = false
  updateContextIndicator()
}

document.getElementById('new-chat-btn').addEventListener('click', newChat)
document.getElementById('clear-chats-btn').addEventListener('click', () => {
  chats.length = 0
  activeChat = null
  saveChats()
  renderHistory()
  renderMessages()
})
sendBtn.addEventListener('click', () => {
  if (sending && activeController) {
    activeController._userStopped = true
    activeController.abort()
    return
  }
  send()
})
input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
})

document.querySelectorAll('.example').forEach(ex => {
  ex.addEventListener('click', () => {
    input.value = ex.textContent
    send()
  })
})

renderHistory()
renderMessages()

// History drawer toggle
const chatDrawer = document.getElementById('chat-drawer')
const drawerBackdrop = document.getElementById('drawer-backdrop')
function openDrawer() {
  chatDrawer?.classList.add('open')
  drawerBackdrop?.classList.add('open')
}
function closeDrawer() {
  chatDrawer?.classList.remove('open')
  drawerBackdrop?.classList.remove('open')
}
document.getElementById('drawer-toggle')?.addEventListener('click', openDrawer)
document.getElementById('drawer-close')?.addEventListener('click', closeDrawer)
drawerBackdrop?.addEventListener('click', closeDrawer)

// ===== FILE CONTEXT INJECTION =====
const ALLOWED_EXTS = ['.txt', '.md', '.py', '.js', '.ts', '.json', '.toml', '.yaml', '.yml', '.csv']
const MAX_FILE_SIZE = 100 * 1024

let attachedFile = null
const fileInput = document.getElementById('file-input')
const fileBtn = document.getElementById('file-upload-btn')
const fileBadge = document.getElementById('file-badge')
const fileBadgeName = document.getElementById('file-badge-name')
const fileBadgeRemove = document.getElementById('file-badge-remove')
const chatMain = document.querySelector('.chat-main')

function clearAttachment() {
  attachedFile = null
  fileInput.value = ''
  fileBadge.classList.add('hidden')
}

function attachFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!ALLOWED_EXTS.includes(ext)) {
    toast('Unsupported file type. Use: ' + ALLOWED_EXTS.join(', '))
    return
  }
  if (file.size > MAX_FILE_SIZE) {
    toast('File too large (max 100KB)')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    attachedFile = { name: file.name, content: reader.result }
    fileBadgeName.textContent = '📎 ' + file.name
    fileBadge.classList.remove('hidden')
  }
  reader.onerror = () => toast('Failed to read file')
  reader.readAsText(file)
}

fileBtn.addEventListener('click', () => fileInput.click())
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) attachFile(fileInput.files[0])
})
fileBadgeRemove.addEventListener('click', clearAttachment)

// drag-and-drop
chatMain.addEventListener('dragover', e => {
  e.preventDefault()
  chatMain.classList.add('dragover')
})
chatMain.addEventListener('dragleave', () => chatMain.classList.remove('dragover'))
chatMain.addEventListener('drop', e => {
  e.preventDefault()
  chatMain.classList.remove('dragover')
  if (e.dataTransfer.files[0]) attachFile(e.dataTransfer.files[0])
})

// ===== MCP TOOLS =====
const toolsPanel = document.getElementById('tools-panel')
const toolsList = document.getElementById('tools-list')
const mcpServersConfig = document.getElementById('mcp-servers-config')
const mcpServersList = document.getElementById('mcp-servers-list')
let mcpTools = []

// ===== TOOL PERMISSIONS =====
const ALLOWED_KEY = 'saturn-allowed-tools'
const allowed = new Set(JSON.parse(localStorage.getItem(ALLOWED_KEY) || '[]'))

function saveAllowed() {
  localStorage.setItem(ALLOWED_KEY, JSON.stringify([...allowed]))
}

const permDialog = document.getElementById('tool-permission')
const permName = document.getElementById('permission-tool-name')
const permArgs = document.getElementById('permission-tool-args')
const permAllow = document.getElementById('perm-allow')
const permAlways = document.getElementById('perm-always')
const permDeny = document.getElementById('perm-deny')

function checkPermission(name, args) {
  if (allowed.has(name)) return Promise.resolve('allow')
  permName.textContent = name
  permArgs.textContent = Object.keys(args || {}).length > 0 ? JSON.stringify(args, null, 2) : '(no arguments)'
  permDialog.classList.remove('hidden')
  return new Promise(resolve => {
    function cleanup() {
      permAllow.removeEventListener('click', onAllow)
      permAlways.removeEventListener('click', onAlways)
      permDeny.removeEventListener('click', onDeny)
      permDialog.classList.add('hidden')
    }
    function onAllow() { cleanup(); resolve('allow') }
    function onAlways() { cleanup(); allowed.add(name); saveAllowed(); resolve('always') }
    function onDeny() { cleanup(); resolve('deny') }
    permAllow.addEventListener('click', onAllow)
    permAlways.addEventListener('click', onAlways)
    permDeny.addEventListener('click', onDeny)
  })
}

async function executeToolCalls(calls, bubble) {
  const results = []
  for (const tc of calls) {
    let args = {}
    try { args = JSON.parse(tc.arguments) } catch { /* partial */ }
    const decision = await checkPermission(tc.name, args)
    if (decision === 'deny') {
      results.push({ name: tc.name, denied: true })
      continue
    }
    try {
      const res = await fetch('/api/mcp/tools/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tc.name, arguments: args }),
      })
      const data = await res.json()
      results.push({ name: tc.name, content: data.content || data })
    } catch (e) {
      results.push({ name: tc.name, error: e.message })
    }
  }
  return results
}

function renderPermissionBadges(calls, results) {
  return calls.map((tc, i) => {
    const r = results[i]
    if (!r) return renderToolCallBadge(tc.name, {})
    if (r.denied) return `<span class="tool-call-badge denied">${esc(tc.name)} [denied]</span>`
    let args = {}
    try { args = JSON.parse(tc.arguments) } catch {}
    const badge = `<span class="tool-call-badge approved">${esc(tc.name)}</span>`
    const content = r.error
      ? `<pre class="tool-result-content" style="color:var(--red)">${esc(r.error)}</pre>`
      : renderToolResult(r.content ? (Array.isArray(r.content) ? r.content : [{ text: JSON.stringify(r.content) }]) : [])
    return badge + content
  }).join('')
}

document.getElementById('tools-toggle').addEventListener('click', () => {
  toolsPanel.classList.toggle('hidden')
  if (!toolsPanel.classList.contains('hidden')) refreshMCPTools()
})

document.getElementById('tools-refresh').addEventListener('click', refreshMCPTools)

document.getElementById('tools-manage').addEventListener('click', () => {
  mcpServersConfig.classList.toggle('hidden')
  if (!mcpServersConfig.classList.contains('hidden')) refreshMCPServers()
})

async function refreshMCPTools() {
  toolsList.innerHTML = '<div class="tool-item"><span style="color:var(--muted)">Loading...</span></div>'
  try {
    const res = await fetch('/api/mcp/tools')
    mcpTools = await res.json()
  } catch {
    mcpTools = []
  }
  renderToolsList()
}

function renderToolsList() {
  toolsList.innerHTML = ''
  if (mcpTools.length === 0) {
    toolsList.innerHTML = '<div class="tool-item"><span style="color:var(--muted)">No tools — add an MCP server first</span></div>'
    return
  }
  mcpTools.forEach(t => {
    const div = document.createElement('div')
    div.className = 'tool-item'
    div.innerHTML = `<span class="tool-name">${esc(t.name)}</span><span class="tool-desc">${esc(t.description)}</span><span class="tool-server">${esc(t.server)}</span>`
    toolsList.appendChild(div)
  })
}

async function refreshMCPServers() {
  mcpServersList.innerHTML = '<div style="color:var(--muted);padding:6px 0">Loading...</div>'
  try {
    const res = await fetch('/api/mcp/servers')
    const servers = await res.json()
    mcpServersList.innerHTML = ''
    if (servers.length === 0) {
      mcpServersList.innerHTML = '<div style="color:var(--muted);padding:6px 0">No servers configured</div>'
      return
    }
    servers.forEach(s => {
      const div = document.createElement('div')
      div.className = 'mcp-server-item'
      div.innerHTML = `<span class="mcp-server-name">${esc(s.name)}</span><span class="mcp-server-url">${esc(s.url)}</span><button class="btn btn-secondary mcp-remove-btn" data-name="${esc(s.name)}">Remove</button>`
      div.querySelector('.mcp-remove-btn').addEventListener('click', async () => {
        await fetch(`/api/mcp/servers/${encodeURIComponent(s.name)}`, { method: 'DELETE' })
        refreshMCPServers()
        refreshMCPTools()
      })
      mcpServersList.appendChild(div)
    })
  } catch {
    mcpServersList.innerHTML = '<div style="color:var(--red);padding:6px 0">Error loading servers</div>'
  }
}

document.getElementById('mcp-add-btn').addEventListener('click', async () => {
  const name = document.getElementById('mcp-name').value.trim()
  const url = document.getElementById('mcp-url').value.trim()
  const token = document.getElementById('mcp-token').value.trim()
  if (!name || !url) { toast('Name and URL required'); return }
  try {
    const res = await fetch('/api/mcp/servers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url, auth_token: token || null }),
    })
    const data = await res.json()
    if (data.added) {
      document.getElementById('mcp-name').value = ''
      document.getElementById('mcp-url').value = ''
      document.getElementById('mcp-token').value = ''
      toast(data.refreshed ? `Added ${name} — tools loaded` : `Added ${name} — refresh failed: ${data.error}`)
      refreshMCPServers()
      refreshMCPTools()
    }
  } catch (e) {
    toast(`Error: ${e.message}`)
  }
})

function renderToolCallBadge(name, args) {
  const argsStr = Object.keys(args || {}).length > 0 ? ` ${JSON.stringify(args)}` : ''
  return `<span class="tool-call-badge">${esc(name)}${esc(argsStr)}</span>`
}

function renderToolCallInline(name, args, running) {
  const formatted = Object.keys(args || {}).length > 0 ? JSON.stringify(args, null, 2) : ''
  const status = running ? '<span class="tool-call-status running">running\u2026</span>' : ''
  const body = formatted ? `<div class="tool-call-args">${esc(formatted)}</div>` : ''
  return `<details class="tool-call-inline"><summary>${esc(name)} ${status}</summary>${body}</details>`
}

function renderToolResultInline(content) {
  if (!content) return ''
  const text = typeof content === 'string' ? content : content.map(c => c.text || JSON.stringify(c)).join('\n')
  return `<details class="tool-result-inline"><summary>Result</summary><pre>${esc(text)}</pre></details>`
}

function renderToolsInline(calls, results) {
  if (!calls || calls.length === 0) return ''
  return calls.map((tc, i) => {
    let args = {}
    try { args = JSON.parse(tc.arguments) } catch { args = {} }
    let html = renderToolCallInline(tc.name, args, false)
    if (results && results[i]) html += renderToolResultInline(results[i])
    return html
  }).join('')
}

function renderToolResult(content) {
  if (!content) return ''
  const text = content.map(c => c.text || JSON.stringify(c)).join('\n')
  return `<div class="tool-result-block"><div class="tool-result-label">Tool Result</div><pre class="tool-result-content">${esc(text)}</pre></div>`
}

// ===== SERVICE CONFIGURATION =====
const configOverlay = document.getElementById('config-overlay')
const PARAMS_KEY = 'saturn-model-params'
const SERVICE_PARAMS_KEY = 'saturn-service-params'
let configScope = 'global' // 'global' or 'service'
let configService = ''     // selected service name when scope=service

function loadAllConfig() {
  try {
    const raw = localStorage.getItem(SERVICE_PARAMS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { global: {}, services: {} }
}

function saveAllConfig(cfg) {
  try { localStorage.setItem(SERVICE_PARAMS_KEY, JSON.stringify(cfg)) } catch { /* ignore */ }
  // sync legacy key for backward compat
  try { localStorage.setItem(PARAMS_KEY, JSON.stringify(cfg.global)) } catch { /* ignore */ }
}

function loadParams() {
  return loadAllConfig().global
}

function saveParams(params) {
  const cfg = loadAllConfig()
  cfg.global = params
  saveAllConfig(cfg)
}

function currentParams() {
  const cfg = loadAllConfig()
  if (configScope === 'service' && configService) return cfg.services[configService] || {}
  return cfg.global
}

function saveCurrentParams(params) {
  const cfg = loadAllConfig()
  if (configScope === 'service' && configService) {
    if (Object.keys(params).length === 0) {
      delete cfg.services[configService]
    } else {
      cfg.services[configService] = params
    }
  } else {
    cfg.global = params
  }
  saveAllConfig(cfg)
}

// merge: per-service overrides global; null values inherit from global
function getActiveParams() {
  const cfg = loadAllConfig()
  const service = document.getElementById('service-select').value
  const merged = { ...cfg.global }
  if (service && cfg.services[service]) {
    for (const [k, v] of Object.entries(cfg.services[service])) {
      if (v !== null && v !== undefined) merged[k] = v
    }
  }
  const out = {}
  for (const [k, v] of Object.entries(merged)) {
    if (v !== null && v !== undefined && k !== 'system_prompt') out[k] = v
  }
  return out
}

function getSystemPrompt() {
  const cfg = loadAllConfig()
  const service = document.getElementById('service-select').value
  if (service && cfg.services[service] && cfg.services[service].system_prompt) return cfg.services[service].system_prompt
  return cfg.global.system_prompt || null
}

// populate the config service selector from available services
function populateConfigServices() {
  const sel = document.getElementById('config-service-select')
  const svcSel = document.getElementById('service-select')
  sel.innerHTML = '<option value="" disabled selected>-- select service --</option>'
  Array.from(svcSel.options).forEach(opt => {
    if (opt.value && !opt.disabled) {
      const o = document.createElement('option')
      o.value = opt.value
      o.textContent = opt.textContent
      sel.appendChild(o)
    }
  })
  // also add services that have saved config
  const cfg = loadAllConfig()
  for (const sid of Object.keys(cfg.services)) {
    if (!sel.querySelector(`option[value="${CSS.escape(sid)}"]`)) {
      const o = document.createElement('option')
      o.value = sid
      o.textContent = sid
      sel.appendChild(o)
    }
  }
}

function applyParamsToUI(params) {
  configOverlay.querySelectorAll('.param-row').forEach(row => {
    const key = row.dataset.param
    const toggle = row.querySelector('.param-toggle')
    const controls = row.querySelector('.param-controls')
    const range = controls.querySelector('input[type="range"]')
    const num = controls.querySelector('input[type="number"]')
    const text = controls.querySelector('input[type="text"]')
    const textarea = controls.querySelector('textarea')

    if (params[key] !== undefined) {
      toggle.dataset.default = 'false'
      toggle.textContent = 'Custom'
      toggle.classList.add('active')
      controls.classList.remove('hidden')
      if (key === 'stop') {
        if (text) text.value = Array.isArray(params[key]) ? params[key].join(', ') : params[key]
      } else if (key === 'system_prompt' || key === 'keep_alive') {
        if (textarea) textarea.value = params[key]
        if (text) text.value = params[key]
      } else {
        if (range) range.value = params[key]
        if (num) num.value = params[key]
      }
    } else {
      toggle.dataset.default = 'true'
      toggle.textContent = 'Default'
      toggle.classList.remove('active')
      controls.classList.add('hidden')
      if (range) {
        const def = range.getAttribute('value')
        range.value = def
        if (num) num.value = def
      } else if (num) {
        num.value = num.getAttribute('value')
      } else if (text) {
        text.value = key === 'keep_alive' ? '5m' : ''
      } else if (textarea) {
        textarea.value = ''
      }
    }
  })
}

function initConfig() {
  configOverlay.querySelectorAll('.param-row').forEach(row => {
    const key = row.dataset.param
    const toggle = row.querySelector('.param-toggle')
    const controls = row.querySelector('.param-controls')
    const range = controls.querySelector('input[type="range"]')
    const num = controls.querySelector('input[type="number"]')
    const text = controls.querySelector('input[type="text"]')
    const textarea = controls.querySelector('textarea')

    toggle.addEventListener('click', () => {
      const isDefault = toggle.dataset.default === 'true'
      if (isDefault) {
        toggle.dataset.default = 'false'
        toggle.textContent = 'Custom'
        toggle.classList.add('active')
        controls.classList.remove('hidden')
      } else {
        toggle.dataset.default = 'true'
        toggle.textContent = 'Default'
        toggle.classList.remove('active')
        controls.classList.add('hidden')
        const params = currentParams()
        delete params[key]
        saveCurrentParams(params)
      }
    })

    if (range && num) {
      range.addEventListener('input', () => {
        num.value = range.value
        const params = currentParams()
        params[key] = parseFloat(range.value)
        saveCurrentParams(params)
      })
      num.addEventListener('input', () => {
        range.value = num.value
        const params = currentParams()
        params[key] = parseFloat(num.value)
        saveCurrentParams(params)
      })
    } else if (num) {
      num.addEventListener('input', () => {
        const params = currentParams()
        params[key] = parseFloat(num.value)
        saveCurrentParams(params)
      })
    } else if (textarea) {
      textarea.addEventListener('input', () => {
        const params = currentParams()
        const val = textarea.value.trim()
        if (val) {
          params[key] = val
        } else {
          delete params[key]
        }
        saveCurrentParams(params)
      })
    } else if (text) {
      text.addEventListener('input', () => {
        const params = currentParams()
        const val = text.value.trim()
        if (key === 'stop') {
          if (val) {
            params[key] = val.split(',').map(s => s.trim()).filter(Boolean)
          } else {
            delete params[key]
          }
        } else {
          if (val) {
            params[key] = val
          } else {
            delete params[key]
          }
        }
        saveCurrentParams(params)
      })
    }
  })

  // scope buttons
  document.getElementById('scope-global').addEventListener('click', () => {
    configScope = 'global'
    configService = ''
    document.getElementById('scope-global').classList.add('active')
    document.getElementById('scope-service').classList.remove('active')
    document.getElementById('config-service-select').classList.add('hidden')
    applyParamsToUI(currentParams())
  })

  document.getElementById('scope-service').addEventListener('click', () => {
    configScope = 'service'
    document.getElementById('scope-global').classList.remove('active')
    document.getElementById('scope-service').classList.add('active')
    const sel = document.getElementById('config-service-select')
    sel.classList.remove('hidden')
    populateConfigServices()
    // pre-select current chat service
    const chatService = document.getElementById('service-select').value
    if (chatService) {
      sel.value = chatService
      configService = chatService
    }
    applyParamsToUI(currentParams())
  })

  document.getElementById('config-service-select').addEventListener('change', (e) => {
    configService = e.target.value
    applyParamsToUI(currentParams())
  })

  // migrate legacy params
  try {
    const legacy = localStorage.getItem(PARAMS_KEY)
    const existing = localStorage.getItem(SERVICE_PARAMS_KEY)
    if (legacy && !existing) {
      const parsed = JSON.parse(legacy)
      if (parsed && typeof parsed === 'object' && !parsed.global) {
        saveAllConfig({ global: parsed, services: {} })
      }
    }
  } catch { /* ignore */ }

  applyParamsToUI(currentParams())
}

// open config overlay — optional serviceName to pre-scope to a service
function openConfig(serviceName) {
  populateConfigServices()
  if (serviceName) {
    configScope = 'service'
    configService = serviceName
    document.getElementById('scope-global').classList.remove('active')
    document.getElementById('scope-service').classList.add('active')
    const sel = document.getElementById('config-service-select')
    sel.classList.remove('hidden')
    // ensure the service appears in the dropdown
    if (!sel.querySelector(`option[value="${CSS.escape(serviceName)}"]`)) {
      const o = document.createElement('option')
      o.value = serviceName
      o.textContent = serviceName
      sel.appendChild(o)
    }
    sel.value = serviceName
  } else {
    configScope = 'global'
    configService = ''
    document.getElementById('scope-global').classList.add('active')
    document.getElementById('scope-service').classList.remove('active')
    document.getElementById('config-service-select').classList.add('hidden')
  }
  applyParamsToUI(currentParams())
  configOverlay.classList.remove('hidden')
}

document.querySelector('.chat-settings-btn').addEventListener('click', () => openConfig(null))

document.getElementById('config-overlay-close').addEventListener('click', () => {
  configOverlay.classList.add('hidden')
})

// close on backdrop click
configOverlay.addEventListener('click', (e) => {
  if (e.target === configOverlay) configOverlay.classList.add('hidden')
})

// close on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !configOverlay.classList.contains('hidden')) {
    configOverlay.classList.add('hidden')
  }
})

document.getElementById('config-reset').addEventListener('click', () => {
  if (configScope === 'service' && configService) {
    const cfg = loadAllConfig()
    delete cfg.services[configService]
    saveAllConfig(cfg)
  } else {
    const cfg = loadAllConfig()
    cfg.global = {}
    saveAllConfig(cfg)
  }
  applyParamsToUI(currentParams())
})

initConfig()

// ===== BRUTUS =====
const brutusGate = document.getElementById('brutus-gate')
const brutusMain = document.getElementById('brutus-main')
const brutusStatus = document.getElementById('brutus-status')
let _brutusRefreshTimer = null

// gate acceptance
document.getElementById('brutus-accept').addEventListener('click', () => {
  brutusGate.classList.add('hidden')
  brutusMain.classList.remove('hidden')
  localStorage.setItem('brutus-accepted', '1')
  loadBrutusQR()
  loadBrutusStatus()
  setTimeout(ensureBrutus, 100)
})

// restore gate state
if (localStorage.getItem('brutus-accepted') === '1') {
  brutusGate.classList.add('hidden')
  brutusMain.classList.remove('hidden')
}

// "Chat with Brutus" button — switch to Chat tab with Brutus selected
document.getElementById('brutus-use-btn').addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
  document.querySelector('[data-tab="chat"]').classList.add('active')
  document.getElementById('chat').classList.add('active')
  serviceSelect.value = '__brutus__'
  loadModels()
  input.focus()
})

// hash-based deep link (for QR code scans) — land on Chat tab in Brutus mode
function checkHash() {
  if (location.hash === '#brutus') {
    if (localStorage.getItem('brutus-accepted') !== '1') {
      localStorage.setItem('brutus-accepted', '1')
    }
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    document.querySelector('[data-tab="chat"]').classList.add('active')
    document.getElementById('chat').classList.add('active')
    // defer Brutus selection until syncServices populates the dropdown
    if ([...serviceSelect.options].some(o => o.value === '__brutus__')) {
      serviceSelect.value = '__brutus__'
      loadModels()
    } else {
      _pendingBrutus = true
    }
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
  setTunnelUI('stopped')
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
})

// refresh button — re-check tunnel status
document.getElementById('brutus-qr-refresh').addEventListener('click', () => loadBrutusQR())

// dashboard status display
async function loadBrutusStatus() {
  try {
    const res = await fetch('/api/brutus/status')
    const data = await res.json()
    renderHealthGrid(data.backends)
    renderRoutingLog(data.routing_log)
    renderBackendsSidebar(data.backends)
    // update header status
    const healthy = data.backends.filter(b => b.healthy).length
    if (data.backends.length === 0) {
      brutusStatus.textContent = '● no backends'
      brutusStatus.style.color = 'var(--red)'
    } else if (healthy === data.backends.length) {
      brutusStatus.textContent = `● ${healthy} backends`
      brutusStatus.style.color = 'var(--green)'
    } else {
      brutusStatus.textContent = `● ${healthy}/${data.backends.length} healthy`
      brutusStatus.style.color = 'var(--accent)'
    }
  } catch {
    brutusStatus.textContent = '● offline'
    brutusStatus.style.color = 'var(--red)'
  }
}

function renderHealthGrid(backends) {
  const grid = document.getElementById('brutus-health-grid')
  if (backends.length === 0) {
    grid.innerHTML = '<div class="brutus-log-empty">Run Discover to see backends</div>'
    return
  }
  grid.innerHTML = ''
  backends.forEach(b => {
    const card = document.createElement('div')
    card.className = 'brutus-health-card'
    const dotColor = b.breaker.open ? 'var(--red)' : b.breaker.failures > 0 ? 'var(--accent)' : 'var(--green)'
    const dot = b.healthy ? '●' : '○'
    const state = b.breaker.open ? `OPEN (${b.breaker.cooldown}s)` : b.breaker.failures > 0 ? `${b.breaker.failures} failures` : 'healthy'
    const models = b.models.length > 0 ? b.models[0] : '—'
    card.innerHTML = `
      <div class="health-card-header">
        <span style="color:${dotColor}">${dot}</span>
        <span class="health-card-name">${b.name}</span>
        <span class="health-card-priority">p${b.priority}</span>
      </div>
      <div class="health-card-detail">${models}</div>
      <div class="health-card-detail" style="color:${dotColor}">${state}</div>
    `
    grid.appendChild(card)
  })
}

function renderRoutingLog(log) {
  const container = document.getElementById('brutus-routing-log')
  if (!log || log.length === 0) {
    container.innerHTML = '<div class="brutus-log-empty">No routing activity yet</div>'
    return
  }
  container.innerHTML = ''
  // show most recent first
  log.slice().reverse().forEach(entry => {
    const div = document.createElement('div')
    div.className = 'brutus-log-entry'
    const time = new Date(entry.ts * 1000).toLocaleTimeString()
    const skipped = entry.skipped.length > 0 ? ` (skipped: ${entry.skipped.join(', ')})` : ''
    div.innerHTML = `<span class="log-time">${time}</span> → <span class="log-service">${entry.service}</span> // ${entry.model} · ${entry.latency_ms}ms${skipped}`
    container.appendChild(div)
  })
}

function renderBackendsSidebar(backends) {
  const container = document.getElementById('brutus-backends')
  if (backends.length === 0) {
    container.innerHTML = '<div class="brutus-backend-item"><span class="name" style="color:var(--muted)">Run Discover first</span></div>'
    return
  }
  container.innerHTML = ''
  backends.forEach(b => {
    const div = document.createElement('div')
    div.className = 'brutus-backend-item'
    const dot = b.healthy ? '●' : '○'
    const color = b.breaker.open ? 'var(--red)' : b.breaker.failures > 0 ? 'var(--accent)' : 'var(--green)'
    div.innerHTML = `<span style="color:${color}">${dot}</span> <span class="name">${b.name}</span> <span style="color:var(--muted)">p${b.priority}</span>`
    container.appendChild(div)
  })
}

// refresh when tab shown, auto-refresh every 5s while active
document.querySelector('[data-tab="brutus"]').addEventListener('click', () => {
  if (!brutusMain.classList.contains('hidden')) {
    loadBrutusQR()
    loadBrutusStatus()
    setTimeout(ensureBrutus, 100)
  }
})

// start/stop auto-refresh based on tab visibility
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'brutus') {
      setTimeout(ensureBrutus, 100)
      if (!_brutusRefreshTimer) {
        _brutusRefreshTimer = setInterval(loadBrutusStatus, 5000)
      }
    } else if (_brutusRefreshTimer) {
      clearInterval(_brutusRefreshTimer)
      _brutusRefreshTimer = null
    }
  })
})

// ===== BRUTUS CONNECTOR =====
const connectorConfigs = {
  opencode: {
    name: 'OpenCode',
    render(url, key) {
      return `<div class="file-path">opencode.json</div>
<pre><code>{
  "provider": {
    "saturn": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "${url}",
        "apiKey": "${key}"
      }
    }
  }
}</code></pre>`
    }
  },
  codex: {
    name: 'Codex',
    render(url, key) {
      return `<div class="file-path">~/.codex/config.toml</div>
<pre><code>model_provider = "saturn"

[model_providers.saturn]
name = "Saturn"
base_url = "${url}"
env_key = "SATURN_API_KEY"
wire_api = "responses"</code></pre>
<p>Then set the env var:</p>
<pre><code>export SATURN_API_KEY=${key}</code></pre>
<p class="connector-note">Note: <code>wire_api = "chat"</code> was deprecated in Feb 2026 and is transitioning to a hard error. Saturn must support the <code>/v1/responses</code> endpoint, or use <code>"responses"</code> with a translation proxy.</p>`
    }
  },
  continue: {
    name: 'Continue',
    render(url, key) {
      return `<div class="file-path">~/.continue/config.yaml</div>
<pre><code>models:
  - name: Saturn
    provider: openai
    model: auto
    apiBase: ${url}
    apiKey: ${key}
    roles: [chat, apply, edit]</code></pre>`
    }
  },
  aider: {
    name: 'Aider',
    render(url, key) {
      return `<p>Run directly:</p>
<pre><code>OPENAI_API_BASE=${url} OPENAI_API_KEY=${key} aider --model openai/auto</code></pre>
<p>Or add to <code>.aider.conf.yml</code>:</p>
<pre><code>openai-api-base: ${url}
openai-api-key: ${key}
model: openai/auto</code></pre>`
    }
  },
  cline: {
    name: 'Cline',
    render(url, key) {
      return `<p>In VS Code:</p>
<p>1. Open Cline settings (gear icon)</p>
<p>2. Select <strong>OpenAI Compatible</strong> as provider</p>
<p>3. Set <strong>Base URL</strong> to your Saturn endpoint</p>
<p>4. Set <strong>API Key</strong> to your Saturn key</p>
<p>5. Set model to <strong>auto</strong></p>`
    }
  },
  cursor: {
    name: 'Cursor',
    render(url, key) {
      return `<p>In Cursor:</p>
<p>1. Open <strong>Settings > Models</strong></p>
<p>2. Enable <strong>Override OpenAI Base URL</strong></p>
<p>3. Set Base URL to your Saturn endpoint</p>
<p>4. Set OpenAI API Key to your Saturn key</p>
<p>5. Select any model — Saturn will route it</p>`
    }
  },
  openclaw: {
    name: 'OpenClaw',
    render(url, key) {
      return `<div class="file-path">~/.openclaw/openclaw.json</div>
<pre><code>{
  "baseUrl": "${url}",
  "apiKey": "${key}"
}</code></pre>`
    }
  },
  'claude-code': {
    name: 'Claude Code',
    render(url, key) {
      return `<p class="connector-note">Claude Code speaks the Anthropic Messages API, not OpenAI. Connecting it to Saturn requires a translation proxy like <strong>LiteLLM</strong> that converts between Anthropic and OpenAI formats.</p>
<p>1. Run a LiteLLM proxy pointed at Saturn:</p>
<pre><code>litellm --model openai/auto --api_base ${url} --api_key ${key}</code></pre>
<p>2. Set Claude Code env vars to point at the proxy:</p>
<pre><code>export ANTHROPIC_BASE_URL=http://localhost:4000
export ANTHROPIC_AUTH_TOKEN=${key}</code></pre>
<p class="connector-note">Security: avoid LiteLLM PyPI versions 1.82.7 and 1.82.8 — those were compromised with credential-stealing malware.</p>`
    }
  },
  generic: {
    name: 'Generic (env vars)',
    render(url, key) {
      return `<p>Works with any OpenAI-compatible tool:</p>
<pre><code>export OPENAI_BASE_URL=${url}
export OPENAI_API_KEY=${key}</code></pre>
<p>Covers OpenCode, Aider, Codex, and most tools that read standard env vars.</p>`
    }
  }
}

function saturnEndpoint() {
  return `${location.protocol}//${location.host}/v1`
}

const connectorAccordion = document.getElementById('connector-accordion')
const connectorToolName = document.getElementById('connector-tool-name')
const connectorStep2Name = document.getElementById('connector-step2-name')
const connectorEndpoint = document.getElementById('connector-endpoint')
const connectorKey = document.getElementById('connector-key')
const connectorInstructions = document.getElementById('connector-instructions')

function showConnector(tool) {
  const cfg = connectorConfigs[tool]
  if (!cfg) return
  const url = saturnEndpoint()
  const key = 'saturn-key'

  // highlight active card
  document.querySelectorAll('.connector-card').forEach(c => c.classList.toggle('active', c.dataset.tool === tool))

  connectorToolName.textContent = cfg.name
  connectorStep2Name.textContent = cfg.name
  connectorEndpoint.textContent = url
  connectorKey.textContent = key
  connectorInstructions.innerHTML = cfg.render(url, key)
  addCopyButtons(connectorInstructions)
  connectorAccordion.classList.remove('hidden')
}

document.getElementById('connector-grid').addEventListener('click', e => {
  const card = e.target.closest('.connector-card')
  if (!card) return
  showConnector(card.dataset.tool)
})

document.getElementById('connector-close').addEventListener('click', () => {
  connectorAccordion.classList.add('hidden')
  document.querySelectorAll('.connector-card').forEach(c => c.classList.remove('active'))
})

// copy buttons in connector
document.querySelectorAll('.connector-copy').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = document.getElementById(btn.dataset.target)
    if (!target) return
    navigator.clipboard.writeText(target.textContent).then(() => {
      const orig = btn.textContent
      btn.textContent = 'Copied!'
      setTimeout(() => btn.textContent = orig, 2000)
    })
  })
})

// key reveal toggle
document.getElementById('connector-key-reveal').addEventListener('click', () => {
  const el = document.getElementById('connector-key')
  const btn = document.getElementById('connector-key-reveal')
  el.classList.toggle('masked')
  btn.textContent = el.classList.contains('masked') ? 'Show' : 'Hide'
})

// test connection button
document.getElementById('connector-test-btn').addEventListener('click', async () => {
  const result = document.getElementById('connector-test-result')
  const btn = document.getElementById('connector-test-btn')
  btn.disabled = true
  btn.textContent = 'Testing...'
  result.textContent = ''
  result.className = 'connector-test-result'
  try {
    const start = performance.now()
    const res = await fetch(saturnEndpoint() + '/models', { signal: AbortSignal.timeout(5000) })
    const ms = Math.round(performance.now() - start)
    if (res.ok) {
      const data = await res.json()
      const models = data.data?.map(m => m.id) || []
      result.textContent = `Connected (${ms}ms) — ${models.length} model${models.length !== 1 ? 's' : ''} available`
      result.classList.add('success')
    } else {
      result.textContent = `Server returned ${res.status}`
      result.classList.add('error')
    }
  } catch (e) {
    result.textContent = `Unreachable — ${e.message}`
    result.classList.add('error')
  }
  btn.disabled = false
  btn.textContent = 'Test Connection'
})
