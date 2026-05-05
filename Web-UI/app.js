// Saturn-n5h: attach admin bearer to /api/admin/* and /api/usage/* fetches
;(function () {
  const ADMIN_PATHS = /\/api\/(admin|usage)(\/|$)/
  const _origFetch = window.fetch.bind(window)
  window.fetch = function (url, opts) {
    try {
      const u = typeof url === 'string' ? url : (url && url.url) || ''
      if (ADMIN_PATHS.test(u)) {
        const tok = sessionStorage.getItem('saturn-admin-token')
        if (tok) {
          opts = opts || {}
          const h = new Headers(opts.headers || {})
          if (!h.has('Authorization')) h.set('Authorization', 'Bearer ' + tok)
          opts.headers = h
        }
      }
    } catch { /* ignore */ }
    return _origFetch(url, opts)
  }
})()

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
    // close ephemeral panels on tab switch
    document.getElementById('tools-panel')?.classList.add('hidden')
    document.getElementById('config-overlay')?.classList.add('hidden')
    // init canvas backgrounds on tab switch
    if (tab.dataset.tab === 'chat') {
      newChat()
      const msgs = document.querySelector('.messages')
      if (msgs) initChatStars(msgs)
      initWelcomeSaturn()
    }
    if (tab.dataset.tab === 'system') {
      loadSystemStatus()
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
  renderer.toneMappingExposure = 0.7
  container.appendChild(renderer.domElement)

  // post-processing
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))

  const clampPass = new ShaderPass(BrightnessClampShader)
  composer.addPass(clampPass)

  const bloom = new UnrealBloomPass(
    new THREE.Vector2(w, h),
    0.9,   // strength
    0.5,   // radius
    0.7    // threshold
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

// (3D bust removed — System page uses dashboard-only layout)

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
    const moon = window.saturnMoons?.find(m => m.name === s.name)
    const isChecked = moon ? moon.selected : false
    div.innerHTML = `
      <input type="checkbox" id="${type}-${i}" ${isChecked ? 'checked' : ''}>
      <span class="name">${s.name}</span>
      ${s.status ? `<span class="status ${statusClass}">${s.status}</span>` : ''}
    `
    // wire checkbox to moon selection
    const cb = div.querySelector('input[type="checkbox"]')
    cb.addEventListener('change', () => {
      const moon = window.saturnMoons.find(m => m.name === s.name)
      if (moon) moon.selected = cb.checked
      syncServices()
    })
    list.appendChild(div)
  })
}

const discoverBtn = document.getElementById('discover-btn')
const servicesList = document.getElementById('services-list')

const scanStatus = document.getElementById('scan-status')
function setScanStatus(msg, kind) {
  if (!scanStatus) return
  scanStatus.textContent = msg || ''
  scanStatus.dataset.kind = kind || ''
}

discoverBtn.addEventListener('click', async () => {
  discoverBtn.disabled = true
  discoverBtn.classList.add('busy')
  setScanStatus('Scanning _saturn._tcp.local. …', 'busy')

  const left = document.querySelector('.discover-left')
  left.classList.add('discovering')
  if (window.saturnDiscover) window.saturnDiscover(true)

  let failed = false
  try {
    Object.keys(_modelCache).forEach(k => delete _modelCache[k])
    const res = await fetch('/api/discover')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    discoveredServices = await res.json()
  } catch (e) {
    discoveredServices = []
    failed = true
    console.error('Discovery failed:', e)
  }

  await Promise.all(discoveredServices.map(async s => {
    try {
      const r = await fetch(`/api/models?service=${encodeURIComponent(s.name)}`)
      s.reachable = r.ok
    } catch {
      s.reachable = false
    }
    s.status = s.reachable ? 'online' : 'unreachable'
  }))

  window.saturnMoons = discoveredServices
    .filter(s => s.status === 'online')
    .map(s => ({ name: s.name, selected: true }))

  const unreachable = discoveredServices.filter(s => !s.reachable)
  if (unreachable.length > 0) {
    toast(`${unreachable.length} service${unreachable.length > 1 ? 's' : ''} unreachable: ${unreachable.map(s => s.name).join(', ')}`, 5000)
  }

  render(servicesList, discoveredServices, 'svc')
  syncServices()
  if (failed) {
    setScanStatus('Scan failed — check that the Saturn server is running.', 'error')
  } else {
    const n = discoveredServices.length
    const u = unreachable.length
    const reach = n - u
    if (n === 0) setScanStatus('No peers found on this LAN.', 'empty')
    else if (u === 0) setScanStatus(`Found ${n} peer${n === 1 ? '' : 's'}.`, 'ok')
    else setScanStatus(`Found ${n} peer${n === 1 ? '' : 's'} — ${reach} reachable, ${u} unreachable.`, 'warn')
  }
  discoverBtn.classList.remove('busy')
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
    if (!res.ok) {
      services = []
    } else {
      services = await res.json()
    }
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
  if (!pw) {
    toast('Enter the admin password')
    document.getElementById('admin-pw').focus()
    return
  }
  try {
    const res = await fetch('/api/admin/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    })
    if (res.ok) {
      adminUnlocked = true
      sessionStorage.setItem('saturn-admin', '1')
      try {
        const body = await res.json()
        if (body && body.token) sessionStorage.setItem('saturn-admin-token', body.token)
      } catch { /* ignore */ }
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
const cloudAdvanced = document.getElementById('cloud-advanced-fields')
const testBtn = document.getElementById('cfg-test')

deploySelect.addEventListener('change', () => {
  const cloud = deploySelect.value === 'cloud'
  cloudFields.classList.toggle('hidden', !cloud)
  networkFields.classList.toggle('hidden', cloud)
  cloudAdvanced.classList.toggle('hidden', !cloud)
  testBtn.classList.toggle('hidden', cloud)
})

const advFields = document.getElementById('advanced-fields')
const advToggle = document.getElementById('advanced-toggle')
if (advToggle) {
  advToggle.addEventListener('click', () => {
    const open = advFields.classList.toggle('hidden')
    advToggle.classList.toggle('open', !open)
  })
}

// Ephemeral keys toggle
document.getElementById('cfg-ephemeral').addEventListener('change', (e) => {
  document.getElementById('ephemeral-fields').classList.toggle('hidden', !e.target.checked)
})

const testStatus = document.getElementById('cfg-test-status')
function setTestStatus(msg, kind) {
  if (!testStatus) return
  if (!msg) {
    testStatus.classList.add('hidden')
    testStatus.textContent = ''
    return
  }
  testStatus.classList.remove('hidden')
  testStatus.textContent = msg
  testStatus.dataset.kind = kind || ''
}

testBtn.addEventListener('click', async () => {
  const baseUrl = document.getElementById('cfg-base-url').value.trim()
  if (!baseUrl) {
    setTestStatus('Enter a Base URL first.', 'error')
    return
  }
  testBtn.disabled = true
  setTestStatus('Testing…', 'busy')
  try {
    const res = await fetch(baseUrl.replace(/\/+$/, '') + '/models', { signal: AbortSignal.timeout(5000) })
    if (res.ok) setTestStatus('Connection OK — endpoint responded.', 'ok')
    else setTestStatus(`HTTP ${res.status} — ${hintForStatus(res.status)}`, 'error')
  } catch (e) {
    const msg = e.name === 'TimeoutError' || /timeout/i.test(e.message)
      ? 'Timed out after 5s — host unreachable or wrong URL.'
      : `Network error: ${e.message}. Check URL, CORS, and that the host is reachable.`
    setTestStatus(msg, 'error')
  }
  testBtn.disabled = false
})

function hintForStatus(code) {
  if (code === 401 || code === 403) return 'auth rejected — check API key.'
  if (code === 404) return 'path not found — confirm /v1 is included in Base URL.'
  if (code === 429) return 'rate-limited — try again later.'
  if (code >= 500) return 'upstream error — backend may be down.'
  return 'unexpected response.'
}

const saveError = document.getElementById('cfg-save-error')
const saveBtn = document.getElementById('cfg-save')
const saveEnableBtn = document.getElementById('cfg-save-enable')

function setSaveError(msg, fieldId) {
  if (!saveError) return
  if (!msg) {
    saveError.classList.add('hidden')
    saveError.textContent = ''
    document.querySelectorAll('[aria-invalid="true"]').forEach(el => el.removeAttribute('aria-invalid'))
    return
  }
  saveError.classList.remove('hidden')
  saveError.textContent = msg
  if (fieldId) {
    const el = document.getElementById(fieldId)
    if (el) {
      el.setAttribute('aria-invalid', 'true')
      el.focus()
    }
  }
}

function validateConfig() {
  const name = document.getElementById('cfg-name').value.trim()
  if (!name) return { ok: false, msg: 'Name is required.', field: 'cfg-name' }
  if (!/^[A-Za-z0-9_-]+$/.test(name)) return { ok: false, msg: 'Name may only contain letters, digits, underscore, hyphen.', field: 'cfg-name' }
  const dup = services.find(s => s.name === name)
  if (dup) return { ok: false, msg: `A service named "${name}" already exists.`, field: 'cfg-name' }
  const deployment = document.getElementById('cfg-deployment').value
  if (deployment === 'cloud') {
    const baseUrl = document.getElementById('cfg-base-url').value.trim()
    if (!baseUrl) return { ok: false, msg: 'Base URL is required for cloud deployments.', field: 'cfg-base-url' }
    try { new URL(baseUrl) } catch { return { ok: false, msg: 'Base URL must be a valid http(s) URL (e.g. https://api.example.com/v1).', field: 'cfg-base-url' } }
    if (!/^https?:/i.test(baseUrl)) return { ok: false, msg: 'Base URL must start with http:// or https://.', field: 'cfg-base-url' }
  }
  if (deployment === 'network') {
    if (!document.getElementById('cfg-host').value.trim()) return { ok: false, msg: 'Host is required for local deployments.', field: 'cfg-host' }
    const port = parseInt(document.getElementById('cfg-net-port').value)
    if (!port || port < 1 || port > 65535) return { ok: false, msg: 'Port must be between 1 and 65535.', field: 'cfg-net-port' }
  }
  return { ok: true }
}

function syncSaveEnabled() {
  const v = validateConfig()
  saveBtn.disabled = !v.ok
  if (saveEnableBtn) saveEnableBtn.disabled = !v.ok
  saveBtn.title = v.ok ? '' : v.msg
}

;['cfg-name','cfg-base-url','cfg-host','cfg-net-port','cfg-deployment'].forEach(id => {
  const el = document.getElementById(id)
  if (!el) return
  el.addEventListener('input', () => { setSaveError(null); syncSaveEnabled() })
  el.addEventListener('change', () => { setSaveError(null); syncSaveEnabled() })
})

async function submitConfig() {
  const v = validateConfig()
  if (!v.ok) { setSaveError(v.msg, v.field); return false }
  setSaveError(null)

  const baseUrl = document.getElementById('cfg-base-url').value.trim()
  const body = {
    name: document.getElementById('cfg-name').value.trim(),
    deployment: document.getElementById('cfg-deployment').value,
    api_type: document.getElementById('cfg-api-type').value,
    priority: parseInt(document.getElementById('cfg-priority').value) || 50,
    base_url: baseUrl,
    api_key_env: document.getElementById('cfg-api-key-env-legacy').value.trim() || null,
    port: parseInt(document.getElementById('cfg-adv-port').value) || 0,
    beacon_enabled: document.getElementById('cfg-ephemeral').checked,
    beacon_provider: document.getElementById('cfg-keygen-url').value.trim() || null,
    spend_limit: parseFloat(document.getElementById('cfg-spend-limit').value) || 0,
    rotation_interval: parseInt(document.getElementById('cfg-rotation').value) || 300,
    expiration_interval: parseInt(document.getElementById('cfg-expiration').value) || 600,
  }

  saveBtn.disabled = true
  if (saveEnableBtn) saveEnableBtn.disabled = true
  const prev = saveBtn.textContent
  saveBtn.textContent = 'Saving…'
  try {
    const res = await fetch('/api/services', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const detail = err.detail || `HTTP ${res.status}`
      const lower = String(detail).toLowerCase()
      let field = null
      if (lower.includes('exist') || lower.includes('duplicate')) field = 'cfg-name'
      else if (lower.includes('url')) field = 'cfg-base-url'
      else if (lower.includes('port')) field = 'cfg-net-port'
      else if (lower.includes('host')) field = 'cfg-host'
      setSaveError(`Save failed: ${detail}`, field)
      return false
    }
  } catch (e) {
    setSaveError(`Network error: ${e.message}. Form was not submitted; try again.`)
    return false
  } finally {
    saveBtn.textContent = prev
    syncSaveEnabled()
  }
  return true
}

document.getElementById('cfg-save').addEventListener('click', async () => {
  const ok = await submitConfig()
  if (!ok) return
  resetConfigForm()
  document.getElementById('config-page').classList.add('hidden')
  document.getElementById('discover-main').classList.remove('hidden')
  await loadServices()
})

if (saveEnableBtn) saveEnableBtn.addEventListener('click', async () => {
  const name = document.getElementById('cfg-name').value.trim()
  const ok = await submitConfig()
  if (!ok) return
  try {
    await fetch(`/api/services/${encodeURIComponent(name)}/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  } catch (e) {
    setSaveError(`Service saved but start failed: ${e.message}. You can start it from the Services list.`)
    await loadServices()
    return
  }
  resetConfigForm()
  document.getElementById('config-page').classList.add('hidden')
  document.getElementById('discover-main').classList.remove('hidden')
  await loadServices()
  discoverBtn.click()
})

syncSaveEnabled()

function resetConfigForm() {
  document.getElementById('cfg-name').value = ''
  document.getElementById('cfg-base-url').value = ''
  document.getElementById('cfg-deployment').value = 'cloud'
  document.getElementById('cfg-api-type').value = 'openai'
  document.getElementById('cfg-enabled').checked = true
  document.getElementById('cfg-priority').value = '10'
  document.getElementById('cfg-adv-port').value = ''
  document.getElementById('cfg-api-key-env-legacy').value = ''
  document.getElementById('cfg-ephemeral').checked = false
  document.getElementById('cfg-keygen-url').value = ''
  document.getElementById('cfg-spend-limit').value = '0'
  document.getElementById('cfg-rotation').value = '300'
  document.getElementById('cfg-expiration').value = '600'
  document.getElementById('cfg-host').value = ''
  document.getElementById('cfg-net-port').value = ''
  cloudFields.classList.remove('hidden')
  networkFields.classList.add('hidden')
  cloudAdvanced.classList.remove('hidden')
  testBtn.classList.add('hidden')
  document.getElementById('ephemeral-fields').classList.add('hidden')
  advFields?.classList.add('hidden')
  advToggle?.classList.remove('open')
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

// ===== MODEL FAVORITES (SAT-sgr.6) =====
const FAVORITES_KEY = 'saturn-favorites'

function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return []
}

function saveFavorites(favs) {
  try { localStorage.setItem(FAVORITES_KEY, JSON.stringify(favs)) } catch { /* ignore */ }
}

function toggleFavorite(modelId) {
  const favs = loadFavorites()
  const idx = favs.indexOf(modelId)
  if (idx >= 0) favs.splice(idx, 1)
  else favs.push(modelId)
  saveFavorites(favs)
  return idx < 0
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

function contextBudget() {
  const params = typeof getActiveParams === 'function' ? getActiveParams() : {}
  return params.num_ctx || TOKEN_BUDGET
}

function updateContextIndicator() {
  const el = document.getElementById('context-indicator')
  const fill = document.getElementById('context-fill')
  const label = document.getElementById('context-label')
  if (activeChat === null || chats[activeChat].messages.length === 0) {
    el.classList.remove('visible', 'warn', 'critical')
    return
  }
  const total = chats[activeChat].messages.reduce((s, m) => s + estimate(m.text), 0)
  const budget = contextBudget()
  const pct = Math.min(total / budget, 1)
  const k = (total / 1000).toFixed(total < 1000 ? 1 : 0)
  const budgetK = (budget / 1000).toFixed(0)
  label.textContent = `~${k}K / ${budgetK}K tokens`
  fill.style.width = `${(pct * 100).toFixed(1)}%`
  el.classList.add('visible')
  el.classList.toggle('warn', pct >= 0.8)
  el.classList.toggle('critical', pct >= 0.95)
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
  // only include services whose Discover checkbox is checked
  const checked = discoveredServices.filter(s => {
    const moon = window.saturnMoons?.find(m => m.name === s.name)
    return moon ? moon.selected : false
  })
  const hasManual = loadEndpoints().length > 0
  const hasAliases = Object.keys(loadAliases()).length > 0
  if (checked.length === 0 && discoveredServices.length === 0 && !hasManual && !hasAliases) {
    serviceSelect.innerHTML = '<option value="" disabled selected>-- discover first --</option>'
    return
  }
  if (checked.length === 0 && !hasManual && !hasAliases) {
    serviceSelect.innerHTML = '<option value="" disabled selected>-- select services in Discover --</option>'
    syncSendBtn()
    return
  }
  // aliases at top (SAT-pse.5)
  const aliases = loadAliases()
  if (Object.keys(aliases).length > 0) {
    for (const [name, target] of Object.entries(aliases)) {
      const opt = document.createElement('option')
      opt.value = `__alias__:${name}`
      opt.textContent = `@ ${name}`
      serviceSelect.appendChild(opt)
    }
    const sep0 = document.createElement('option')
    sep0.disabled = true
    sep0.textContent = '────────────'
    serviceSelect.appendChild(sep0)
  }
  checked.forEach(s => {
    const opt = document.createElement('option')
    opt.value = s.name
    opt.textContent = `⊙ ${s.name}`
    serviceSelect.appendChild(opt)
  })
  // manual endpoints (SAT-pse.6)
  const eps = loadEndpoints()
  if (eps.length > 0) {
    const sep1 = document.createElement('option')
    sep1.disabled = true
    sep1.textContent = '── manual ──'
    serviceSelect.appendChild(sep1)
    eps.forEach(ep => {
      const opt = document.createElement('option')
      opt.value = `__manual__:${ep.name}`
      opt.textContent = `◇ ${ep.name}`
      serviceSelect.appendChild(opt)
    })
  }
  // Auto-route option
  const sep = document.createElement('option')
  sep.disabled = true
  sep.textContent = '────────────'
  serviceSelect.appendChild(sep)
  const autoOpt = document.createElement('option')
  autoOpt.value = '__brutus__'
  autoOpt.textContent = '⊛ Auto-route'
  autoOpt.title = 'Pick the lowest-priority healthy peer automatically. Fails over on health-check failure.'
  serviceSelect.appendChild(autoOpt)
  // restore previous selection or saved pref
  const saved = prev || loadPrefs().service
  if (saved && [...serviceSelect.options].some(o => o.value === saved)) {
    serviceSelect.value = saved
  }
  // apply deferred auto-route selection from hash deep-link
  if (_pendingAutoRoute) {
    serviceSelect.value = '__brutus__'
    _pendingAutoRoute = false
  }
  loadModels()
}
let _pendingAutoRoute = false
let _pendingAliasModel = null

function syncSendBtn() {
  const valid = modelSelect.value && !modelSelect.selectedOptions[0]?.disabled
  sendBtn.disabled = sending ? false : !valid
  sendBtn.title = valid ? '' : 'Select a valid model first'
}

const selDot = document.querySelector('.sel-dot')
function setDot(state) {
  selDot.className = 'sel-dot' + (state ? ` ${state}` : '')
}

// fetch models from selected service
const _modelCache = {}
let _modelController = null

async function loadModels() {
  const name = serviceSelect.value
  const errorHint = document.getElementById('model-error')
  errorHint.hidden = true
  errorHint.textContent = ''
  if (_modelController) _modelController.abort()
  if (!name) {
    modelSelect.innerHTML = '<option value="" disabled selected>-- select service --</option>'
    setDot('idle')
    syncSendBtn()
    return
  }
  if (name === '__brutus__') {
    modelSelect.innerHTML = '<option value="auto" selected>auto (best available)</option>'
    setDot('')
    syncSendBtn()
    return
  }
  // manual endpoint (SAT-pse.6)
  if (name.startsWith('__manual__:')) {
    const epName = name.slice(11)
    const ep = loadEndpoints().find(e => e.name === epName)
    if (!ep) return
    const cacheKey = `__manual__:${epName}`
    if (_modelCache[cacheKey]) {
      applyModels(_modelCache[cacheKey])
      return
    }
    modelSelect.innerHTML = '<option value="" disabled selected>loading...</option>'
    setDot('loading')
    syncSendBtn()
    try {
      const res = await fetch(`/api/proxy/models?base_url=${encodeURIComponent(ep.url)}`)
      const list = await res.json()
      _modelCache[cacheKey] = { ok: true, models: list }
      applyModels(_modelCache[cacheKey])
    } catch (e) {
      _modelCache[cacheKey] = { ok: false, error: e.message }
      applyModels(_modelCache[cacheKey])
    }
    return
  }
  // use cache if available
  if (_modelCache[name]) {
    applyModels(_modelCache[name])
    return
  }
  modelSelect.innerHTML = '<option value="" disabled selected>loading...</option>'
  setDot('loading')
  syncSendBtn()
  const ctrl = _modelController = new AbortController()
  try {
    const res = await fetch(`/api/models?service=${encodeURIComponent(name)}`, { signal: ctrl.signal })
    if (ctrl !== _modelController) return
    if (!res.ok) {
      const body = await res.text()
      throw new Error(body.includes('Failed to fetch') ? 'Service unreachable' : `HTTP ${res.status}`)
    }
    const list = await res.json()
    _modelCache[name] = { ok: true, models: list }
    applyModels(_modelCache[name])
  } catch (e) {
    if (e.name === 'AbortError') return
    _modelCache[name] = { ok: false, error: e.message }
    applyModels(_modelCache[name])
  }
}

function applyModels(cached) {
  const errorHint = document.getElementById('model-error')
  errorHint.hidden = true
  errorHint.textContent = ''
  if (!cached.ok) {
    modelSelect.innerHTML = '<option value="" disabled selected>-- error --</option>'
    errorHint.textContent = cached.error === 'Service unreachable' ? 'Service unreachable' : 'Could not load models'
    errorHint.hidden = false
    setDot('error')
    syncSendBtn()
    return
  }
  modelSelect.innerHTML = ''
  if (cached.models.length === 0) {
    modelSelect.innerHTML = '<option value="" disabled selected>-- no models --</option>'
    setDot('error')
    syncSendBtn()
    return
  }
  // sort favorites to top (SAT-sgr.6)
  const favs = loadFavorites()
  const sorted = [...cached.models].sort((a, b) => {
    const af = favs.includes(a.id) ? 0 : 1
    const bf = favs.includes(b.id) ? 0 : 1
    return af - bf
  })
  let addedDivider = false
  sorted.forEach(m => {
    const isFav = favs.includes(m.id)
    if (!isFav && !addedDivider && favs.length > 0 && sorted.some(x => favs.includes(x.id))) {
      const divOpt = document.createElement('option')
      divOpt.disabled = true
      divOpt.textContent = '────────'
      modelSelect.appendChild(divOpt)
      addedDivider = true
    }
    const opt = document.createElement('option')
    opt.value = m.id
    opt.textContent = isFav ? `\u2605 ${m.id}` : m.id
    modelSelect.appendChild(opt)
  })
  // resolve pending alias model (SAT-pse.5)
  if (_pendingAliasModel) {
    const target = _pendingAliasModel
    _pendingAliasModel = null
    if ([...modelSelect.options].some(o => o.value === target)) {
      modelSelect.value = target
      savePrefs({ model: target })
      setDot('')
      syncSendBtn()
      return
    }
  }
  const savedModel = loadPrefs().model
  if (savedModel && [...modelSelect.options].some(o => o.value === savedModel)) {
    modelSelect.value = savedModel
  }
  setDot('')
  syncSendBtn()
}

serviceSelect.addEventListener('change', () => {
  const val = serviceSelect.value
  // resolve alias (SAT-pse.5)
  if (val.startsWith('__alias__:')) {
    const name = val.slice(10)
    const aliases = loadAliases()
    const target = aliases[name]
    if (target) {
      // switch to the real service, then auto-select model
      const real = [...serviceSelect.options].find(o => o.value === target.service)
      if (real) {
        serviceSelect.value = target.service
        savePrefs({ service: target.service })
        _pendingAliasModel = target.model
        loadModels()
        return
      }
    }
  }
  savePrefs({ service: val })
  loadModels()
})
modelSelect.addEventListener('change', () => {
  savePrefs({ model: modelSelect.value })
  syncSendBtn()
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
  const favs = loadFavorites()
  const sorted = [...allModels].sort((a, b) => {
    const af = favs.includes(a.id) ? 0 : 1
    const bf = favs.includes(b.id) ? 0 : 1
    return af - bf
  })
  let addedDivider = false
  sorted.forEach(m => {
    const isFav = favs.includes(m.id)
    if (!isFav && !addedDivider && sorted.some(x => favs.includes(x.id))) {
      const hr = document.createElement('hr')
      hr.className = 'model-divider'
      modelList.appendChild(hr)
      addedDivider = true
    }
    const div = document.createElement('div')
    div.className = 'model-item'
    div.dataset.model = m.id
    div.dataset.service = m.service
    const star = document.createElement('button')
    star.className = 'model-star' + (isFav ? ' starred' : '')
    star.textContent = isFav ? '\u2605' : '\u2606'
    star.title = 'Toggle favorite'
    star.addEventListener('click', (e) => {
      e.stopPropagation()
      toggleFavorite(m.id)
      renderModelList()
      // re-render model selector dropdown too
      const svc = serviceSelect.value
      if (svc && _modelCache[svc]) applyModels(_modelCache[svc])
    })
    div.appendChild(star)
    const dot = document.createElement('span')
    dot.className = 'status-dot'
    div.appendChild(dot)
    const name = document.createElement('span')
    name.className = 'model-name'
    name.textContent = m.id
    div.appendChild(name)
    const svcSpan = document.createElement('span')
    svcSpan.className = 'model-service'
    svcSpan.textContent = m.service
    div.appendChild(svcSpan)
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
        ? `auto → ${m.service || ''} // ${m.model || ''}`
        : `${m.service || ''} // ${m.model || ''}`
      div.innerHTML = `
        <div class="meta">${metaLabel}</div>
        <div class="bubble markdown-body">${toolHTML}${renderWithThinking(m.text)}</div>
      `
      if (m.usage) {
        const c = cost(m.model, m.usage)
        const uel = document.createElement('div')
        uel.className = 'token-usage'
        let label = `${m.usage.prompt_tokens || 0} in / ${m.usage.completion_tokens || 0} out`
        if (m.usage.total_tokens) label += ` / ${m.usage.total_tokens} total`
        if (c > 0) label += ` · $${c < 0.01 ? c.toFixed(6) : c.toFixed(4)}`
        uel.textContent = label
        div.appendChild(uel)
      }
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

  const service = serviceSelect.value
  const model = modelSelect.value
  if (!service || !model) {
    toast('Select a service and model first (run Discover)')
    return
  }
  if (!checkSpendLimit()) return
  input.value = ''
  input.style.height = 'auto'

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
  const isManual = service.startsWith('__manual__:')
  const manualEp = isManual ? loadEndpoints().find(e => e.name === service.slice(11)) : null

  // create assistant placeholder with streaming cursor
  const aDiv = document.createElement('div')
  aDiv.className = 'msg assistant'
  const displayService = isManual ? service.slice(11) : service
  aDiv.innerHTML = `
    <div class="meta">${isBrutus ? 'auto-route // routing...' : `${esc(displayService)} // ${esc(model)}`}</div>
    <div class="bubble markdown-body"><span class="cursor">▊</span></div>
  `
  messagesEl.appendChild(aDiv)
  messagesEl.scrollTop = messagesEl.scrollHeight

  const bubble = aDiv.querySelector('.bubble')
  let full = ''
  let toolCalls = []
  let usage = null
  sending = true
  sendBtn.textContent = 'Stop'
  sendBtn.classList.add('btn-stop')
  sendBtn.disabled = false

  let actualService = service, actualModel = model

  let endpoint, payload
  if (isManual && manualEp) {
    endpoint = '/api/proxy/chat'
    payload = { base_url: manualEp.url, model, messages: compacted, api_type: manualEp.api_type, ...getActiveParams() }
  } else if (isBrutus) {
    endpoint = '/api/system/chat'
    payload = { messages: compacted, ...getActiveParams() }
  } else {
    endpoint = '/api/chat'
    payload = { service, model, messages: compacted, ...getActiveParams() }
  }
  if (thinkingState !== 'off') payload.thinking = thinkingState

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
        actualService = res.headers.get('X-Saturn-Service') || 'unknown'
        actualModel = res.headers.get('X-Saturn-Model') || 'auto'
        const skipped = res.headers.get('X-Saturn-Skipped')
        const latency = res.headers.get('X-Saturn-Latency')
        const meta = aDiv.querySelector('.meta')
        meta.textContent = `auto → ${actualService} // ${actualModel}${latency ? ` · ${latency}ms` : ''}`
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
            if (chunk.usage) usage = chunk.usage
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
      // display token usage + cost (SAT-pse.2, SAT-pse.3)
      if (usage) {
        const c = cost(actualModel, usage)
        if (c > 0) recordSpend(c)
        const usageEl = document.createElement('div')
        usageEl.className = 'token-usage'
        let label = `${usage.prompt_tokens || 0} in / ${usage.completion_tokens || 0} out`
        if (usage.total_tokens) label += ` / ${usage.total_tokens} total`
        if (c > 0) label += ` · $${c < 0.01 ? c.toFixed(6) : c.toFixed(4)}`
        usageEl.textContent = label
        aDiv.appendChild(usageEl)
      }
      chat.messages.push({
        role: 'assistant', text: full || '[empty response]',
        service: actualService, model: actualModel,
        routedBy: isBrutus ? 'brutus' : undefined,
        toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        toolResults: toolResults.length > 0 ? toolResults : undefined,
        usage: usage || undefined,
      })
      saveChats()
      streamState = 'idle'
      // report usage to backend for quota tracking (SAT-2n8.2)
      if (usage) reportUsage(usage.prompt_tokens || 0, usage.completion_tokens || 0)
      updateRateLimit()
      checkContextForSummarize()
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
      syncSendBtn()
    }
  }
  activeController = null
  streamState = streamState === 'streaming' ? 'idle' : streamState
  sending = false
  sendBtn.textContent = 'Send'
  sendBtn.classList.remove('btn-stop')
  syncSendBtn()
  updateContextIndicator()
}

document.getElementById('new-chat-btn').addEventListener('click', newChat)
document.getElementById('clear-chats-btn').addEventListener('click', () => {
  if (!confirm('Delete all conversations? This cannot be undone.')) return
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
setDot('idle')
syncSendBtn()

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
const chatGate = document.getElementById('chat-gate')
const chatShell = document.getElementById('chat-shell')
const chatAccept = document.getElementById('chat-accept')

function syncChatGate() {
  const accepted = localStorage.getItem('chat-accepted') === '1'
  chatGate.classList.toggle('hidden', accepted)
  chatShell.classList.toggle('hidden', !accepted)
}
syncChatGate()
chatAccept.addEventListener('click', () => {
  localStorage.setItem('chat-accepted', '1')
  syncChatGate()
})

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

fileBtn?.addEventListener('click', () => fileInput.click())

document.getElementById('plus-menu-btn')?.addEventListener('click', (e) => {
  e.stopPropagation()
  document.getElementById('plus-menu')?.classList.toggle('hidden')
})
document.getElementById('plus-attach')?.addEventListener('click', () => {
  document.getElementById('plus-menu')?.classList.add('hidden')
  fileInput.click()
})
document.getElementById('plus-mcp')?.addEventListener('click', () => {
  document.getElementById('plus-menu')?.classList.add('hidden')
  document.getElementById('tools-toggle')?.click()
})
document.addEventListener('click', (e) => {
  const menu = document.getElementById('plus-menu')
  if (!menu || menu.classList.contains('hidden')) return
  if (e.target.closest('#plus-menu') || e.target.closest('#plus-menu-btn')) return
  menu.classList.add('hidden')
})
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

document.getElementById('tools-toggle').addEventListener('click', () => {
  if (!document.getElementById('tools-panel').classList.contains('hidden')) refreshMCPServers()
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

// ===== STYLE PREFIXES (SAT-sgr.3) =====
const STYLE_PREFIXES = {
  '': '',
  concise: 'Be concise. Give short, direct answers. Avoid unnecessary elaboration.',
  detailed: 'Be thorough and detailed. Explain your reasoning step by step. Provide comprehensive answers.',
  code: 'Respond with code only. No explanations unless asked. Use comments for clarity.',
}

// ===== THINKING TOGGLE (SAT-pse.1) =====
let thinkingState = 'off' // off | on | deep
const thinkingBtn = document.getElementById('thinking-toggle')
if (thinkingBtn) {
  thinkingBtn.addEventListener('click', () => {
    const cycle = { off: 'on', on: 'deep', deep: 'off' }
    thinkingState = cycle[thinkingState]
    thinkingBtn.dataset.state = thinkingState
    const labels = { off: 'Thinking: Off', on: 'Thinking: On', deep: 'Thinking: Deep' }
    thinkingBtn.title = labels[thinkingState]
  })
}

// ===== MANUAL ENDPOINTS (SAT-pse.6) =====
const ENDPOINTS_KEY = 'saturn-endpoints'

function loadEndpoints() {
  try {
    const raw = localStorage.getItem(ENDPOINTS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return []
}

function saveEndpoints(eps) {
  try { localStorage.setItem(ENDPOINTS_KEY, JSON.stringify(eps)) } catch { /* ignore */ }
}

function renderEndpoints() {
  const list = document.getElementById('manual-ep-list')
  if (!list) return
  const eps = loadEndpoints()
  list.innerHTML = ''
  eps.forEach((ep, i) => {
    const row = document.createElement('div')
    row.className = 'alias-row'
    row.innerHTML = `<span class="alias-tag">${esc(ep.name)}</span> <span class="alias-target">${esc(ep.url)} (${esc(ep.api_type)})</span>
      <button class="btn btn-secondary alias-rm" data-idx="${i}">×</button>`
    row.querySelector('.alias-rm').addEventListener('click', () => {
      const all = loadEndpoints()
      all.splice(i, 1)
      saveEndpoints(all)
      renderEndpoints()
      syncServices()
    })
    list.appendChild(row)
  })
}

document.getElementById('ep-add')?.addEventListener('click', () => {
  const name = document.getElementById('ep-name').value.trim()
  const url = document.getElementById('ep-url').value.trim()
  const type = document.getElementById('ep-type').value
  if (!name || !url) return
  const eps = loadEndpoints()
  eps.push({ name, url, api_type: type })
  saveEndpoints(eps)
  document.getElementById('ep-name').value = ''
  document.getElementById('ep-url').value = ''
  renderEndpoints()
  syncServices()
})

// ===== MODEL ALIASES (SAT-pse.5) =====
const ALIASES_KEY = 'saturn-aliases'

function loadAliases() {
  try {
    const raw = localStorage.getItem(ALIASES_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {}
}

function saveAliases(aliases) {
  try { localStorage.setItem(ALIASES_KEY, JSON.stringify(aliases)) } catch { /* ignore */ }
}

function renderAliases() {
  const list = document.getElementById('alias-list')
  if (!list) return
  const aliases = loadAliases()
  list.innerHTML = ''
  for (const [name, target] of Object.entries(aliases)) {
    const row = document.createElement('div')
    row.className = 'alias-row'
    row.innerHTML = `<span class="alias-tag">@${esc(name)}</span> → <span class="alias-target">${esc(target.service)} / ${esc(target.model)}</span>
      <button class="btn btn-secondary alias-rm" data-alias="${esc(name)}">×</button>`
    row.querySelector('.alias-rm').addEventListener('click', () => {
      const a = loadAliases()
      delete a[name]
      saveAliases(a)
      renderAliases()
    })
    list.appendChild(row)
  }
  // populate alias-service select
  const sel = document.getElementById('alias-service')
  if (sel) {
    sel.innerHTML = '<option value="" disabled selected>service</option>'
    discoveredServices.forEach(s => {
      const o = document.createElement('option')
      o.value = s.name
      o.textContent = s.name
      sel.appendChild(o)
    })
  }
}

document.getElementById('alias-add')?.addEventListener('click', () => {
  const name = document.getElementById('alias-name').value.trim()
  const service = document.getElementById('alias-service').value
  const model = document.getElementById('alias-model').value.trim()
  if (!name || !service || !model) return
  const aliases = loadAliases()
  aliases[name] = { service, model }
  saveAliases(aliases)
  document.getElementById('alias-name').value = ''
  document.getElementById('alias-model').value = ''
  renderAliases()
})

// ===== COST TRACKING (SAT-pse.3) =====
const SPEND_KEY = 'saturn-spend'
const PRICING = {
  // prices per million tokens { input, output }
  'gpt-4o': { input: 2.5, output: 10 },
  'gpt-4o-mini': { input: 0.15, output: 0.6 },
  'gpt-4-turbo': { input: 10, output: 30 },
  'gpt-4': { input: 30, output: 60 },
  'gpt-3.5-turbo': { input: 0.5, output: 1.5 },
  'o1': { input: 15, output: 60 },
  'o1-mini': { input: 3, output: 12 },
  'o3': { input: 10, output: 40 },
  'o3-mini': { input: 1.1, output: 4.4 },
  'o4-mini': { input: 1.1, output: 4.4 },
  'claude-3-5-sonnet': { input: 3, output: 15 },
  'claude-3-5-haiku': { input: 0.8, output: 4 },
  'claude-3-opus': { input: 15, output: 75 },
  'claude-sonnet-4': { input: 3, output: 15 },
  'claude-opus-4': { input: 15, output: 75 },
  'claude-haiku-4': { input: 0.8, output: 4 },
  'gemini-2.0-flash': { input: 0.1, output: 0.4 },
  'gemini-2.5-pro': { input: 1.25, output: 10 },
  'gemini-2.5-flash': { input: 0.15, output: 0.6 },
  'deepseek-chat': { input: 0.27, output: 1.1 },
  'deepseek-reasoner': { input: 0.55, output: 2.19 },
  'llama-3.1-8b': { input: 0, output: 0 },
  'llama-3.1-70b': { input: 0, output: 0 },
  'llama-3.3-70b': { input: 0, output: 0 },
  'mistral-large': { input: 2, output: 6 },
  'mixtral-8x7b': { input: 0.24, output: 0.24 },
  'qwen-2.5-72b': { input: 0, output: 0 },
}

function loadSpend() {
  try {
    const raw = localStorage.getItem(SPEND_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { daily: {}, total: 0 }
}

function saveSpend(spend) {
  try { localStorage.setItem(SPEND_KEY, JSON.stringify(spend)) } catch { /* ignore */ }
}

function pricing(model) {
  if (!model) return null
  const lower = model.toLowerCase()
  for (const [key, price] of Object.entries(PRICING)) {
    if (lower.includes(key)) return price
  }
  return null
}

function cost(model, u) {
  if (!u) return 0
  const p = pricing(model)
  if (!p) return 0
  return ((u.prompt_tokens || 0) * p.input + (u.completion_tokens || 0) * p.output) / 1_000_000
}

function recordSpend(amount) {
  if (amount <= 0) return
  const spend = loadSpend()
  const today = new Date().toISOString().slice(0, 10)
  spend.daily[today] = (spend.daily[today] || 0) + amount
  spend.total = (spend.total || 0) + amount
  saveSpend(spend)
}

function todaySpend() {
  const spend = loadSpend()
  return spend.daily[new Date().toISOString().slice(0, 10)] || 0
}

function spendLimit() {
  const cfg = loadAllConfig()
  return cfg.global.spend_limit || 0
}

function checkSpendLimit() {
  const limit = spendLimit()
  if (limit <= 0) return true
  if (todaySpend() >= limit) {
    toast(`Daily spend limit ($${limit.toFixed(2)}) reached`)
    return false
  }
  return true
}

function updateBudgetSummary() {
  const el = document.getElementById('budget-summary')
  if (!el) return
  const spend = loadSpend()
  const today = todaySpend()
  const limit = spendLimit()
  let html = `<span>Today: $${today.toFixed(4)}</span>`
  html += ` · <span>Total: $${(spend.total || 0).toFixed(4)}</span>`
  if (limit > 0) html += ` · <span>Limit: $${limit.toFixed(2)}</span>`
  el.innerHTML = html
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
// per-provider param allowlists (SAT-sgr.8)
const OPENAI_ALLOWED = new Set(['temperature', 'max_tokens', 'top_p', 'frequency_penalty',
  'presence_penalty', 'seed', 'stop', 'response_format'])
const OLLAMA_ALLOWED = new Set(['temperature', 'max_tokens', 'top_p', 'top_k', 'frequency_penalty',
  'presence_penalty', 'repeat_penalty', 'repeat_last_n', 'min_p', 'seed', 'stop',
  'mirostat', 'mirostat_tau', 'mirostat_eta', 'num_ctx', 'num_batch', 'keep_alive',
  'tfs_z', 'typical_p'])
const ANTHROPIC_ALLOWED = new Set(['temperature', 'max_tokens', 'top_p', 'top_k', 'stop'])
const PARAM_ALLOWLISTS = { openai: OPENAI_ALLOWED, ollama: OLLAMA_ALLOWED, anthropic: ANTHROPIC_ALLOWED }

function getServiceApiType(name) {
  const svc = discoveredServices.find(s => s.name === name)
  return svc?.api_type || 'openai'
}

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
    if (v !== null && v !== undefined && k !== 'system_prompt' && k !== 'spend_limit') out[k] = v
  }
  // per-provider param filtering (SAT-sgr.8)
  if (service && service !== '__brutus__') {
    const apiType = getServiceApiType(service)
    const allowed = PARAM_ALLOWLISTS[apiType]
    if (allowed) {
      for (const k of Object.keys(out)) {
        if (!allowed.has(k)) delete out[k]
      }
    }
  }
  return out
}

function getSystemPrompt() {
  const cfg = loadAllConfig()
  const service = document.getElementById('service-select').value
  let prompt = null
  if (service && cfg.services[service] && cfg.services[service].system_prompt) prompt = cfg.services[service].system_prompt
  else prompt = cfg.global.system_prompt || null

  // inject style prefix (SAT-sgr.3)
  const style = document.querySelector('input[name="chat-style-radio"]:checked')?.value || ''
  const prefix = STYLE_PREFIXES[style] || ''
  if (!prefix) return prompt
  if (!prompt) return prefix
  return prefix + '\n\n' + prompt
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

    // response_format uses a select + textarea (SAT-sgr.5)
    if (key === 'response_format') {
      const sel = document.getElementById('response-format-type')
      const schema = document.getElementById('response-format-schema')
      if (params[key]) {
        toggle.dataset.default = 'false'
        toggle.textContent = 'Custom'
        toggle.classList.add('active')
        controls.classList.remove('hidden')
        sel.value = params[key].type || 'text'
        schema.classList.toggle('hidden', sel.value !== 'json_schema')
        if (sel.value === 'json_schema' && params[key].json_schema?.schema) {
          schema.value = JSON.stringify(params[key].json_schema.schema, null, 2)
        }
      } else {
        toggle.dataset.default = 'true'
        toggle.textContent = 'Default'
        toggle.classList.remove('active')
        controls.classList.add('hidden')
        sel.value = 'text'
        schema.classList.add('hidden')
        schema.value = ''
      }
      return
    }

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

  function syncOllama() {
    const section = document.getElementById('ollama-section')
    if (!section) return
    if (configScope === 'global') { section.classList.remove('hidden'); return }
    const svc = discoveredServices.find(s => s.name === configService)
    section.classList.toggle('hidden', svc ? svc.api_type !== 'ollama' : true)
  }

  // scope buttons
  document.getElementById('scope-global').addEventListener('click', () => {
    configScope = 'global'
    configService = ''
    document.getElementById('scope-global').classList.add('active')
    document.getElementById('scope-service').classList.remove('active')
    document.getElementById('config-service-select').classList.add('hidden')
    syncOllama()
    applyParamsToUI(currentParams())
  })

  document.getElementById('scope-service').addEventListener('click', () => {
    configScope = 'service'
    document.getElementById('scope-global').classList.remove('active')
    document.getElementById('scope-service').classList.add('active')
    const sel = document.getElementById('config-service-select')
    sel.classList.remove('hidden')
    populateConfigServices()
    configService = ''
    syncOllama()
    applyParamsToUI(currentParams())
  })

  document.getElementById('config-service-select').addEventListener('change', (e) => {
    configService = e.target.value
    syncOllama()
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
  updateBudgetSummary()
  renderAliases()
  renderEndpoints()
  configOverlay.classList.remove('hidden')
}

document.querySelectorAll('.chat-settings-btn').forEach(b => b.addEventListener('click', (e) => {
  e.stopPropagation()
  const popup = document.getElementById('chat-settings-popup')
  if (!popup) return
  popup.classList.toggle('hidden')
  if (!popup.classList.contains('hidden')) {
    const svc = document.getElementById('service-select')
    const cur = document.getElementById('chat-current-service')
    if (cur) cur.textContent = (svc && svc.value) ? svc.value : '—'
  }
}))

document.addEventListener('click', (e) => {
  const popup = document.getElementById('chat-settings-popup')
  if (!popup || popup.classList.contains('hidden')) return
  if (e.target.closest('#chat-settings-popup') || e.target.closest('.chat-settings-btn')) return
  popup.classList.add('hidden')
})

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

// ===== NAMED PRESETS (SAT-sgr.2) =====
const PRESETS_KEY = 'saturn-presets'

function loadPresets() {
  try {
    const raw = localStorage.getItem(PRESETS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return []
}

function savePresets(presets) {
  try { localStorage.setItem(PRESETS_KEY, JSON.stringify(presets)) } catch { /* ignore */ }
}

function refreshPresetSelect() {
  const sel = document.getElementById('preset-select')
  const prev = sel.value
  sel.innerHTML = '<option value="" selected>-- no preset --</option>'
  loadPresets().forEach((p, i) => {
    const opt = document.createElement('option')
    opt.value = i
    opt.textContent = p.name
    sel.appendChild(opt)
  })
  if (prev && sel.querySelector(`option[value="${prev}"]`)) sel.value = prev
  document.getElementById('preset-delete').disabled = !sel.value
}

document.getElementById('preset-save').addEventListener('click', () => {
  const name = prompt('Preset name:')
  if (!name) return
  const params = currentParams()
  const model = modelSelect.value
  const sys = params.system_prompt || null
  const preset = { name, params: { ...params }, model, systemPrompt: sys }
  const presets = loadPresets()
  const existing = presets.findIndex(p => p.name === name)
  if (existing >= 0) presets[existing] = preset
  else presets.push(preset)
  savePresets(presets)
  refreshPresetSelect()
  document.getElementById('preset-select').value = presets.length - 1
  document.getElementById('preset-delete').disabled = false
  toast(`Preset "${name}" saved`)
})

document.getElementById('preset-delete').addEventListener('click', () => {
  const sel = document.getElementById('preset-select')
  const idx = parseInt(sel.value)
  if (isNaN(idx)) return
  const presets = loadPresets()
  const name = presets[idx]?.name
  presets.splice(idx, 1)
  savePresets(presets)
  refreshPresetSelect()
  toast(`Preset "${name}" deleted`)
})

document.getElementById('preset-select').addEventListener('change', (e) => {
  const idx = parseInt(e.target.value)
  document.getElementById('preset-delete').disabled = isNaN(idx)
  if (isNaN(idx)) return
  const presets = loadPresets()
  const preset = presets[idx]
  if (!preset) return
  saveCurrentParams(preset.params)
  applyParamsToUI(preset.params)
  if (preset.model && [...modelSelect.options].some(o => o.value === preset.model)) {
    modelSelect.value = preset.model
  }
  toast(`Loaded preset "${preset.name}"`)
})

refreshPresetSelect()

// ===== RESPONSE FORMAT (SAT-sgr.5) =====
const responseFormatType = document.getElementById('response-format-type')
const responseFormatSchema = document.getElementById('response-format-schema')

if (responseFormatType) {
  responseFormatType.addEventListener('change', () => {
    responseFormatSchema.classList.toggle('hidden', responseFormatType.value !== 'json_schema')
    const params = currentParams()
    if (responseFormatType.value === 'text') {
      delete params.response_format
    } else if (responseFormatType.value === 'json_object') {
      params.response_format = { type: 'json_object' }
    } else {
      let schema = {}
      try { schema = JSON.parse(responseFormatSchema.value || '{}') } catch { /* ignore */ }
      params.response_format = { type: 'json_schema', json_schema: { name: 'custom', strict: true, schema } }
    }
    saveCurrentParams(params)
  })

  responseFormatSchema.addEventListener('input', () => {
    if (responseFormatType.value !== 'json_schema') return
    const params = currentParams()
    let schema = {}
    try { schema = JSON.parse(responseFormatSchema.value || '{}') } catch { /* ignore */ }
    params.response_format = { type: 'json_schema', json_schema: { name: 'custom', strict: true, schema } }
    saveCurrentParams(params)
  })
}

// ===== STYLE PRESETS (SAT-sgr.3) — constants defined earlier in file =====

// ===== MODEL FAVORITES (SAT-sgr.6) — functions defined earlier in file =====

// ===== CONVERSATION EXPORT (SAT-sgr.7) =====
function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

document.getElementById('export-json')?.addEventListener('click', () => {
  if (activeChat === null) { toast('No active conversation'); return }
  const chat = chats[activeChat]
  const data = chat.messages.map(m => ({ role: m.role, content: m.text }))
  download(`saturn-${chat.name || 'chat'}.json`, JSON.stringify(data, null, 2), 'application/json')
  toast('Exported JSON')
})

document.getElementById('export-md')?.addEventListener('click', () => {
  if (activeChat === null) { toast('No active conversation'); return }
  const chat = chats[activeChat]
  const lines = [`# ${chat.name || 'Saturn Chat'}`, '']
  for (const m of chat.messages) {
    const label = m.role === 'user' ? '**You**' : m.role === 'assistant' ? '**Assistant**' : `**${m.role}**`
    lines.push(`### ${label}`, '', m.text, '')
  }
  download(`saturn-${chat.name || 'chat'}.md`, lines.join('\n'), 'text/markdown')
  toast('Exported Markdown')
})

// ===== SYSTEM =====
const systemGate = document.getElementById('system-gate')
const systemMain = document.getElementById('system-main')
const systemStatus = document.getElementById('system-status')
const remoteMain = document.getElementById('proxy-shell')
const proxyEmpty = document.getElementById('proxy-empty')
const proxyActive = document.getElementById('proxy-active')
const proxyMode = document.getElementById('proxy-mode')
let _systemRefreshTimer = null

function remoteAccepted() {
  return localStorage.getItem('brutus-accepted') === '1'
}

function syncSystemGate() {
  const accepted = remoteAccepted()
  systemGate.classList.toggle('hidden', accepted)
  remoteMain.classList.toggle('hidden', !accepted)
}

let activeSubtab = 'status'

function showSubtab(name, focus) {
  activeSubtab = name
  document.querySelectorAll('.subtab').forEach(btn => {
    const active = btn.dataset.subtab === name
    btn.classList.toggle('active', active)
    btn.setAttribute('aria-selected', active)
    btn.setAttribute('tabindex', active ? '0' : '-1')
    if (active && focus) btn.focus()
  })
  document.querySelectorAll('.subtab-page').forEach(page => page.classList.toggle('active', page.id === 'subtab-' + name))
  history.replaceState(null, '', '#system/' + name)
  if (name === 'status') {
    loadSystemStatus()
    return
  }
  if (name === 'remote') {
    syncSystemGate()
    if (remoteAccepted()) loadSystemQR()
  }
}

const subtabs = Array.from(document.querySelectorAll('.subtab'))
subtabs.forEach(btn => {
  btn.addEventListener('click', () => showSubtab(btn.dataset.subtab))
})

document.querySelector('.system-subtabs-nav').addEventListener('keydown', e => {
  const idx = subtabs.indexOf(document.activeElement)
  if (idx < 0) return
  let next
  if (e.key === 'ArrowRight') next = (idx + 1) % subtabs.length
  if (e.key === 'ArrowLeft') next = (idx - 1 + subtabs.length) % subtabs.length
  if (e.key === 'Home') next = 0
  if (e.key === 'End') next = subtabs.length - 1
  if (next != null) {
    e.preventDefault()
    showSubtab(subtabs[next].dataset.subtab, true)
  }
})

// gate acceptance
document.getElementById('system-accept').addEventListener('click', () => {
  localStorage.setItem('brutus-accepted', '1')
  syncSystemGate()
  loadSystemQR()
  loadSystemStatus()
})

syncSystemGate()

// hash-based deep link — #brutus backward compat, also support #system and #system/<subtab>
function switchToTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
  document.querySelector(`[data-tab="${name}"]`)?.classList.add('active')
  document.getElementById(name)?.classList.add('active')
  updateIndicator()
}

function checkHash() {
  const hash = location.hash.replace('#', '')
  if (hash === 'brutus' || hash === 'system' || hash.startsWith('system/')) {
    if (hash === 'brutus') {
      switchToTab('chat')
      if ([...serviceSelect.options].some(o => o.value === '__brutus__')) {
        serviceSelect.value = '__brutus__'
        loadModels()
      } else {
        _pendingAutoRoute = true
      }
      return
    }
    switchToTab('system')
    const sub = hash.split('/')[1]
    if (sub && ['status', 'remote', 'integrate'].includes(sub)) {
      showSubtab(sub)
    }
  }
}
window.addEventListener('hashchange', checkHash)
checkHash()

// QR code
const tunnelStatus = document.getElementById('proxy-tunnel-status')
const tunnelStartBtn = document.getElementById('proxy-tunnel-start')
const tunnelStopBtn = document.getElementById('proxy-tunnel-stop')

function renderQR(url) {
  const container = document.getElementById('proxy-qr')
  const urlText = document.getElementById('proxy-url')
  if (!url) {
    container.innerHTML = ''
    container.classList.add('empty')
    urlText.textContent = 'No tunnel active'
    return
  }
  container.classList.remove('empty')
  const target = url.replace(/\/$/, '') + '/#system'
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
  const running = status === 'running'
  proxyMode.textContent = running ? 'Mode: Tunnel Active' : 'Mode: LAN Only'
  proxyMode.classList.toggle('active', running)
  proxyEmpty.classList.toggle('hidden', running)
  proxyActive.classList.toggle('hidden', !running)
  if (running) {
    tunnelStatus.textContent = '● tunnel active'
    tunnelStatus.style.color = 'var(--green)'
    tunnelStopBtn.classList.remove('hidden')
    renderQR(url)
    return
  }
  tunnelStatus.textContent = '● stopped'
  tunnelStatus.style.color = 'var(--red)'
  tunnelStopBtn.classList.add('hidden')
  renderQR(null)
}

async function loadSystemQR() {
  try {
    const res = await fetch('/api/system/tunnel/status')
    const data = await res.json()
    if (data.status === 'running' && data.url) {
      setTunnelUI('running', data.url)
      return
    }
  } catch { /* fall through */ }
  setTunnelUI('stopped')
}

function resetTunnelStart(msg) {
  tunnelStartBtn.disabled = false
  tunnelStartBtn.textContent = 'Start Tunnel'
  if (msg) toast(msg)
}

// start tunnel
tunnelStartBtn.addEventListener('click', async () => {
  tunnelStartBtn.disabled = true
  tunnelStartBtn.textContent = 'Starting...'
  tunnelStatus.textContent = '● connecting...'
  tunnelStatus.style.color = 'var(--accent)'
  try {
    const res = await fetch('/api/system/tunnel/start', { method: 'POST' })
    const data = await res.json().catch(() => ({}))
    const error = data.error || data.detail
    if (!res.ok || error) {
      setTunnelUI('stopped')
      resetTunnelStart(error || 'Tunnel failed to start')
      return
    }
    if (!data.url) {
      setTunnelUI('stopped')
      resetTunnelStart('Tunnel failed to start')
      return
    }
    setTunnelUI('running', data.url)
    resetTunnelStart()
  } catch (e) {
    setTunnelUI('stopped')
    resetTunnelStart('Failed to start tunnel: ' + e.message)
  }
})

// stop tunnel
tunnelStopBtn.addEventListener('click', async () => {
  tunnelStopBtn.disabled = true
  tunnelStopBtn.textContent = 'Stopping...'
  try {
    await fetch('/api/system/tunnel/stop', { method: 'POST' })
  } catch { /* ok */ }
  setTunnelUI('stopped')
  tunnelStopBtn.disabled = false
  tunnelStopBtn.textContent = 'Stop Tunnel'
})

// dashboard status display
async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system/status')
    const data = await res.json()
    renderHealthGrid(data.backends)
    renderRoutingLog(data.routing_log)
    const healthy = data.backends.filter(b => b.healthy).length
    if (data.backends.length === 0) {
      systemStatus.textContent = '● no backends'
      systemStatus.style.color = 'var(--red)'
    } else if (healthy === data.backends.length) {
      systemStatus.textContent = `● ${healthy} backends`
      systemStatus.style.color = 'var(--green)'
    } else {
      systemStatus.textContent = `● ${healthy}/${data.backends.length} healthy`
      systemStatus.style.color = 'var(--accent)'
    }
  } catch {
    systemStatus.textContent = '● offline'
    systemStatus.style.color = 'var(--red)'
  }
}

function renderHealthGrid(backends) {
  const grid = document.getElementById('system-health-grid')
  if (backends.length === 0) {
    grid.innerHTML = '<div class="system-log-empty">Run Discover to see backends</div>'
    return
  }
  grid.innerHTML = ''
  backends.forEach(b => {
    const card = document.createElement('div')
    card.className = 'system-health-card'
    card.dataset.healthy = String(b.healthy === true)
    const hasModels = b.models?.length > 0 && b.models[0]
    const breaker = b.breaker || { open: false, failures: 0, cooldown: 0 }
    const dot = b.healthy === true || b.healthy === false ? '●' : '○'
    const dotColor = b.healthy === true ? 'var(--green)' : b.healthy === false ? 'var(--red)' : 'var(--fg-muted)'
    const stateColor = breaker.open ? 'var(--red)' : breaker.failures > 0 ? 'var(--accent)' : b.healthy === true ? 'var(--green)' : 'var(--fg-muted)'
    const state = breaker.open ? `OPEN (${breaker.cooldown}s)` : breaker.failures > 0 ? `${breaker.failures} failures` : hasModels ? 'ready' : 'reachable'
    const models = hasModels ? b.models[0] : 'no model loaded'
    card.innerHTML = `
      <div class="health-card-header">
        <span style="color:${dotColor}">${dot}</span>
        <span class="health-card-name">${b.name}</span>
        <span class="health-card-priority">p${b.priority}</span>
      </div>
      <div class="health-card-detail">${models}</div>
      <div class="health-card-detail" style="color:${stateColor}">${state}</div>
    `
    grid.appendChild(card)
  })
}

function renderRoutingLog(log) {
  const container = document.getElementById('system-routing-log')
  if (!log || log.length === 0) {
    container.innerHTML = `
      <div class="system-log-empty">No routing activity yet</div>
      <div class="system-log-empty-hint">Activity appears here when requests are routed through auto-route.</div>
    `
    return
  }
  container.innerHTML = ''
  log.slice().reverse().forEach(entry => {
    const div = document.createElement('div')
    div.className = 'system-log-entry'
    const time = new Date(entry.ts * 1000).toLocaleTimeString()
    const skipped = entry.skipped.length > 0 ? ` (skipped: ${entry.skipped.join(', ')})` : ''
    div.innerHTML = `<span class="log-time">${time}</span> → <span class="log-service">${entry.service}</span> // ${entry.model} · ${entry.latency_ms}ms${skipped}`
    container.appendChild(div)
  })
}

// refresh when tab shown, auto-refresh every 5s while active
document.querySelector('[data-tab="system"]').addEventListener('click', () => {
  if (!systemMain) return
  loadSystemStatus()
  if (remoteAccepted()) loadSystemQR()
})

// start/stop auto-refresh based on tab visibility
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'system') {
      if (!_systemRefreshTimer) {
        _systemRefreshTimer = setInterval(loadSystemStatus, 5000)
      }
    } else if (_systemRefreshTimer) {
      clearInterval(_systemRefreshTimer)
      _systemRefreshTimer = null
    }
  })
})

// ===== CONNECTOR =====
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

// ===== RATE LIMIT UX (SAT-2n8.1) =====

async function updateRateLimit() {
  const bar = document.getElementById('rate-limit-bar')
  const fill = document.getElementById('rate-limit-fill')
  const label = document.getElementById('rate-limit-label')
  const banner = document.getElementById('rate-limit-banner')
  try {
    const res = await fetch('/api/rate-limit/status')
    if (!res.ok) return
    const data = await res.json()
    const used = data.rpm.limit - data.rpm.remaining
    const pct = Math.min(100, (used / data.rpm.limit) * 100)
    bar.classList.remove('hidden')
    fill.style.width = pct + '%'
    fill.className = 'rate-limit-fill' + (pct >= 100 ? ' critical' : pct >= 80 ? ' warn' : '')
    label.textContent = `${data.rpm.remaining}/${data.rpm.limit} RPM`
    if (pct >= 100) {
      banner.className = 'rate-limit-banner critical'
      banner.textContent = 'Rate limit reached. Requests will be throttled.'
      banner.classList.remove('hidden')
    } else if (pct >= 80) {
      banner.className = 'rate-limit-banner warn'
      banner.textContent = `Approaching rate limit (${Math.round(pct)}% used)`
      banner.classList.remove('hidden')
    } else {
      banner.classList.add('hidden')
    }
  } catch { /* offline */ }
}

// ===== USAGE TRACKING (SAT-2n8.2) =====

async function reportUsage(tokensIn, tokensOut) {
  if (tokensIn <= 0 && tokensOut <= 0) return
  try {
    await fetch('/api/usage/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tokens_in: tokensIn, tokens_out: tokensOut })
    })
  } catch { /* best-effort */ }
}

async function loadSystemUsage() {
  const el = document.getElementById('system-usage')
  if (!el) return
  try {
    const res = await fetch('/api/usage')
    if (!res.ok) return
    const data = await res.json()
    el.innerHTML = `
      <div class="usage-stat"><span class="usage-stat-label">Requests</span><span class="usage-stat-value">${data.requests}</span></div>
      <div class="usage-stat"><span class="usage-stat-label">Tokens In</span><span class="usage-stat-value">${(data.tokens_in || 0).toLocaleString()}</span></div>
      <div class="usage-stat"><span class="usage-stat-label">Tokens Out</span><span class="usage-stat-value">${(data.tokens_out || 0).toLocaleString()}</span></div>
    `
  } catch { /* offline */ }
}

// ===== MODEL FILTER ADMIN (SAT-2n8.3) =====

async function loadModelFilter() {
  const input = document.getElementById('model-filter-input')
  if (!input) return
  try {
    const res = await fetch('/api/admin/config')
    if (!res.ok) return
    const cfg = await res.json()
    if (cfg.model_filter) input.value = cfg.model_filter
  } catch { /* ignore */ }
}

document.getElementById('model-filter-save')?.addEventListener('click', async () => {
  const input = document.getElementById('model-filter-input')
  try {
    const res = await fetch('/api/admin/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_filter: input.value })
    })
    if (res.ok) toast('Model filter updated')
  } catch (e) {
    toast('Failed to save: ' + e.message)
  }
})

// ===== AUTO-SUMMARIZATION (SAT-2n8.4) =====

let summarizeDismissed = false

function checkContextForSummarize() {
  if (summarizeDismissed || activeChat === null) return
  const chat = chats[activeChat]
  if (!chat || chat.messages.length < 4) return
  const budget = contextBudget()
  const total = chat.messages.reduce((s, m) => s + estimate(m.text || ''), 0)
  const pct = total / budget
  const notice = document.getElementById('summarize-notice')
  if (pct >= 0.8) {
    notice.classList.remove('hidden')
  } else {
    notice.classList.add('hidden')
  }
}

document.getElementById('summarize-btn')?.addEventListener('click', async () => {
  if (activeChat === null) return
  const chat = chats[activeChat]
  if (!chat || chat.messages.length < 4) return

  const service = serviceSelect.value
  const model = modelSelect.value
  if (!service || !model) {
    toast('Select a service and model first')
    return
  }

  const btn = document.getElementById('summarize-btn')
  btn.disabled = true
  btn.textContent = 'Summarizing...'

  // take the older messages (all except last 4)
  const older = chat.messages.slice(0, -4)
  const recent = chat.messages.slice(-4)

  const prompt = [
    { role: 'system', content: 'Summarize the following conversation concisely, preserving key facts, decisions, and context. Output only the summary.' },
    ...older.map(m => ({ role: m.role, content: m.text }))
  ]

  try {
    const isBrutus = service === '__brutus__'
    const isManual = service.startsWith('__manual__:')
    const manualEp = isManual ? loadEndpoints().find(e => e.name === service.slice(11)) : null

    let endpoint, payload
    if (isManual && manualEp) {
      endpoint = '/api/proxy/chat'
      payload = { base_url: manualEp.url, model, messages: prompt, api_type: manualEp.api_type, max_tokens: 1024 }
    } else if (isBrutus) {
      endpoint = '/api/system/chat'
      payload = { messages: prompt, max_tokens: 1024 }
    } else {
      endpoint = '/api/chat'
      payload = { service, model, messages: prompt, max_tokens: 1024 }
    }

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    let summary = ''
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6)
        if (raw === '[DONE]') continue
        try {
          const obj = JSON.parse(raw)
          const delta = obj.choices?.[0]?.delta?.content
          if (delta) summary += delta
        } catch { /* skip */ }
      }
    }

    if (summary) {
      chat.messages = [
        { role: 'assistant', text: `[Summary of ${older.length} earlier messages]\n\n${summary}` },
        ...recent
      ]
      saveChats()
      renderMessages()
      toast(`Summarized ${older.length} messages`)
    }
  } catch (e) {
    toast('Summarization failed: ' + e.message)
  }

  btn.disabled = false
  btn.textContent = 'Summarize older messages'
  document.getElementById('summarize-notice').classList.add('hidden')
})

document.getElementById('summarize-dismiss')?.addEventListener('click', () => {
  summarizeDismissed = true
  document.getElementById('summarize-notice').classList.add('hidden')
})

// load rate limit + usage on system tab, periodically during chat
function initPhase3() {
  loadModelFilter()
  updateRateLimit()
  loadSystemUsage()
}

// refresh rate limit after each send
const _origSendEndHook = () => {
  updateRateLimit()
  checkContextForSummarize()
}

// hook into system tab activation
const _origLoadSystemStatus = typeof loadSystemStatus === 'function' ? loadSystemStatus : null
if (_origLoadSystemStatus) {
  const _wrapped = loadSystemStatus
  window._loadSystemStatusWrapped = async function() {
    await _wrapped()
    await loadSystemUsage()
  }
}

// run on init
initPhase3()

// --- qj5.6: edit-sent-message ---
function ensureEditAffordance(userDiv) {
  if (!userDiv || userDiv.querySelector('.edit-btn')) return
  const btn = document.createElement('button')
  btn.className = 'edit-btn'
  btn.type = 'button'
  btn.textContent = 'Edit'
  btn.setAttribute('aria-label', 'Edit message')
  btn.title = 'Edit message'
  userDiv.appendChild(btn)
}

function indexOfMsg(div) {
  const all = Array.from(document.querySelectorAll('#messages .msg'))
  return all.indexOf(div)
}

function beginEdit(userDiv) {
  if (userDiv.querySelector('.edit-textarea')) return
  const bubble = userDiv.querySelector('.bubble')
  if (!bubble) return
  const original = bubble.textContent
  const ta = document.createElement('textarea')
  ta.className = 'edit-textarea'
  ta.value = original
  const actions = document.createElement('div')
  actions.className = 'edit-actions'
  const save = document.createElement('button')
  save.type = 'button'
  save.className = 'edit-save'
  save.textContent = 'Save & regenerate'
  const cancel = document.createElement('button')
  cancel.type = 'button'
  cancel.className = 'edit-cancel'
  cancel.textContent = 'Cancel'
  actions.appendChild(save)
  actions.appendChild(cancel)
  bubble.replaceWith(ta)
  userDiv.appendChild(actions)
  ta.focus()

  cancel.addEventListener('click', () => {
    const restored = document.createElement('div')
    restored.className = 'bubble'
    restored.textContent = original
    ta.replaceWith(restored)
    actions.remove()
  })

  save.addEventListener('click', () => {
    const newText = ta.value.trim()
    if (!newText) return
    const idx = indexOfMsg(userDiv)
    let sib = userDiv.nextElementSibling
    while (sib) {
      const next = sib.nextElementSibling
      if (sib.classList.contains('msg')) sib.remove()
      sib = next
    }
    userDiv.remove()
    if (typeof activeChat !== 'undefined' && activeChat !== null && chats[activeChat]) {
      const msgs = chats[activeChat].messages
      if (idx >= 0 && idx < msgs.length) {
        msgs.length = idx
        saveChats()
      }
    }
    if (typeof input !== 'undefined' && typeof send === 'function') {
      input.value = newText
      send()
    }
  })
}

document.addEventListener('mouseover', (e) => {
  const userDiv = e.target.closest && e.target.closest('.msg.user')
  if (userDiv) ensureEditAffordance(userDiv)
})

document.addEventListener('click', (e) => {
  const btn = e.target.closest && e.target.closest('.msg.user .edit-btn')
  if (!btn) return
  e.stopPropagation()
  beginEdit(btn.closest('.msg.user'))
})

const _msgs = document.getElementById('messages')
if (_msgs) {
  new MutationObserver((muts) => {
    for (const m of muts) {
      m.addedNodes.forEach(n => {
        if (n.nodeType === 1 && n.classList && n.classList.contains('msg') && n.classList.contains('user')) {
          ensureEditAffordance(n)
        }
      })
    }
  }).observe(_msgs, { childList: true })
  document.querySelectorAll('#messages .msg.user').forEach(ensureEditAffordance)
}

// --- Saturn-hft (qj5.13 commit-2): admin Configure page ---

const AC_FIELDS = [
  ['model_filter', 'string'],
  ['max_budget', 'float'],
  ['budget_duration', 'string'],
  ['admin_session_ttl_s', 'int'],
  ['admin_token_env', 'string'],
  ['runner_token_env', 'string'],
  ['admin_password_env', 'string'],
  ['bind_host', 'string'],
  ['runner_bind_host', 'string'],
  ['trusted_proxies', 'list'],
  ['cors_origins', 'list'],
  ['rate_rpm', 'int'],
  ['rate_tpm', 'int'],
  ['rate_concurrent_per_ip', 'int'],
  ['max_budget_usd', 'float'],
  ['budget_period', 'string'],
  ['per_ip_max_budget_usd', 'float'],
  ['public_routes', 'list'],
  ['require_auth_on_v1', 'bool'],
  ['proxy_models_method', 'string'],
  ['redact_proxy_keys_in_logs', 'bool'],
  ['mcp_allowed_urls', 'list'],
  ['mcp_auth_token_envs', 'json'],
  ['trust_mode', 'string'],
  ['trusted_node_ids', 'list'],
  ['beacon_max_budget_usd', 'float'],
]

let _acDirty = false
let _acPoller = null

function _acClearErrors() {
  document.querySelectorAll('#admin-configure-page .field-error').forEach(e => e.remove())
}

async function loadAdminConfigure() {
  try {
    const res = await fetch('/api/admin/config')
    if (!res.ok) return
    const cfg = await res.json()
    for (const [name, type] of AC_FIELDS) {
      const el = document.getElementById('ac-' + name)
      if (!el) continue
      if (document.activeElement === el) continue
      const v = cfg[name]
      if (type === 'bool') el.checked = !!v
      else if (v === null || v === undefined) { /* leave as-is */ }
      else if (type === 'list') el.value = Array.isArray(v) ? v.join(',') : ''
      else if (type === 'json') el.value = (typeof v === 'object' && v) ? JSON.stringify(v) : ''
      else el.value = String(v)
    }
  } catch { /* ignore */ }
}

async function saveAdminConfigure() {
  _acClearErrors()
  const body = {}
  for (const [name, type] of AC_FIELDS) {
    const el = document.getElementById('ac-' + name)
    if (!el) continue
    if (type === 'bool') { body[name] = el.checked; continue }
    const raw = (el.value || '').trim()
    if (raw === '') continue
    if (type === 'int') {
      const n = parseInt(raw, 10)
      if (Number.isFinite(n)) body[name] = n
    } else if (type === 'float') {
      const n = parseFloat(raw)
      if (Number.isFinite(n)) body[name] = n
    } else if (type === 'list') {
      body[name] = raw.split(',').map(s => s.trim()).filter(Boolean)
    } else if (type === 'json') {
      try { body[name] = JSON.parse(raw) } catch { /* skip malformed */ }
    } else body[name] = raw
  }
  const res = await fetch('/api/admin/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (res.status === 422) {
    let parsed = {}
    try { parsed = await res.json() } catch {}
    const errs = (parsed.detail && parsed.detail.errors) || []
    for (const msg of errs) {
      const lower = String(msg).toLowerCase()
      for (const [name] of AC_FIELDS) {
        if (lower.includes(name)) {
          const el = document.getElementById('ac-' + name)
          if (el) {
            const region = el.closest('label, fieldset')
            const span = document.createElement('span')
            span.className = 'field-error'
            span.textContent = msg
            region.appendChild(span)
          }
          break
        }
      }
    }
    return
  }
  if (res.ok) {
    _acDirty = false
    if (typeof toast === 'function') toast('Saved')
  }
}

function showAdminConfigure() {
  const page = document.getElementById('admin-configure-page')
  if (!page) return
  page.classList.remove('hidden')
  loadAdminConfigure()
  if (!_acPoller) {
    _acPoller = setInterval(() => {
      const p = document.getElementById('admin-configure-page')
      if (!p || p.classList.contains('hidden') || _acDirty) return
      loadAdminConfigure()
    }, 500)
  }
}

function hideAdminConfigure() {
  document.getElementById('admin-configure-page')?.classList.add('hidden')
}

function checkAdminConfigureRoute() {
  const path = window.location.pathname
  const hash = window.location.hash
  if (path === '/admin/configure' || path === '/configure' || hash === '#admin' || hash === '#configure') {
    showAdminConfigure()
  }
}

document.querySelectorAll('#admin-configure-page input, #admin-configure-page select').forEach(el => {
  el.addEventListener('input', () => { _acDirty = true })
  el.addEventListener('change', () => { _acDirty = true })
})
document.getElementById('ac-save')?.addEventListener('click', saveAdminConfigure)
document.getElementById('ac-close')?.addEventListener('click', hideAdminConfigure)
document.getElementById('admin-configure-btn')?.addEventListener('click', () => {
  window.location.hash = 'admin'
  showAdminConfigure()
})
document.getElementById('admin-configure-nav-btn')?.addEventListener('click', () => {
  window.location.hash = 'admin'
  showAdminConfigure()
})
window.addEventListener('hashchange', checkAdminConfigureRoute)
checkAdminConfigureRoute()

// --- Saturn-6sb (qj5.13 commit-3): per-service editor ---

let _editingService = null

async function loadPerServiceList() {
  const list = document.getElementById('per-service-list')
  if (!list) return
  try {
    const r = await fetch('/api/services')
    if (!r.ok) return
    const services = await r.json()
    if (!Array.isArray(services)) return
    list.innerHTML = ''
    for (const s of services) {
      const row = document.createElement('div')
      row.className = 'service-row'
      row.dataset.service = s.name
      const label = document.createElement('span')
      label.textContent = `${s.name} — priority ${s.priority != null ? s.priority : '?'}`
      row.appendChild(label)
      const editBtn = document.createElement('button')
      editBtn.type = 'button'
      editBtn.textContent = 'Edit'
      editBtn.addEventListener('click', () => editService(s))
      row.appendChild(editBtn)
      const delBtn = document.createElement('button')
      delBtn.type = 'button'
      delBtn.textContent = 'Delete'
      delBtn.addEventListener('click', () => deleteService(s.name))
      row.appendChild(delBtn)
      list.appendChild(row)
    }
  } catch { /* ignore */ }
}

function _showServiceForm() {
  document.getElementById('per-service-form')?.classList.remove('hidden')
  document.getElementById('per-service-add')?.classList.add('hidden')
}
function _hideServiceForm() {
  document.getElementById('per-service-form')?.classList.add('hidden')
  document.getElementById('per-service-add')?.classList.remove('hidden')
}

function editService(s) {
  _editingService = s.name
  const setIf = (id, v) => { const e = document.getElementById(id); if (e) e.value = v == null ? '' : String(v) }
  setIf('cfg-name', s.name)
  const nameEl = document.getElementById('cfg-name')
  if (nameEl) nameEl.disabled = true
  setIf('cfg-base-url', s.base_url || (s.upstream && s.upstream.base_url) || '')
  setIf('cfg-priority', s.priority != null ? s.priority : 50)
  setIf('cfg-deployment', s.deployment || 'local')
  setIf('cfg-api-type', s.api_type || 'ollama')
  _showServiceForm()
}

function newService() {
  _editingService = null
  const nameEl = document.getElementById('cfg-name')
  if (nameEl) { nameEl.value = ''; nameEl.disabled = false }
  const setIf = (id, v) => { const e = document.getElementById(id); if (e) e.value = v }
  setIf('cfg-base-url', '')
  setIf('cfg-priority', '50')
  setIf('cfg-api-key-env', '')
  _showServiceForm()
}

async function saveService() {
  const get = (id) => (document.getElementById(id)?.value || '').trim()
  const name = get('cfg-name')
  if (!name) return
  const body = {
    name,
    deployment: get('cfg-deployment') || 'local',
    api_type: get('cfg-api-type') || 'ollama',
    priority: parseInt(get('cfg-priority') || '50', 10) || 50,
    upstream: {
      base_url: get('cfg-base-url'),
      api_key_env: get('cfg-api-key-env') || null,
    },
  }
  const path = _editingService ? `/api/services/${encodeURIComponent(_editingService)}` : '/api/services'
  const method = _editingService ? 'PUT' : 'POST'
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (res.ok) {
    _hideServiceForm()
    _editingService = null
    await loadPerServiceList()
  }
}

async function deleteService(name) {
  if (!window.confirm(`Delete service ${name}?`)) return
  await fetch(`/api/services/${encodeURIComponent(name)}`, { method: 'DELETE' })
  await loadPerServiceList()
}

document.getElementById('per-service-add')?.addEventListener('click', newService)
document.getElementById('per-service-save')?.addEventListener('click', saveService)
document.getElementById('per-service-cancel')?.addEventListener('click', () => {
  _hideServiceForm()
  _editingService = null
})

if (document.getElementById('per-service-list')) {
  loadPerServiceList()
  setInterval(() => {
    const ae = document.activeElement
    const inForm = ae && ae.id && (ae.id.startsWith('cfg-') || ae.id.startsWith('per-service'))
    if (!inForm) loadPerServiceList()
  }, 1000)
}

// --- Saturn-7j3 (qj5.16.13 commit-3): known-nodes UI ---

async function loadKnownNodes() {
  const pinned = document.getElementById('kn-pinned-list')
  const rej = document.getElementById('kn-rejections-list')
  if (!pinned && !rej) return
  let data
  try {
    const r = await fetch('/api/admin/known-nodes')
    if (!r.ok) return
    data = await r.json()
  } catch { return }
  if (pinned) {
    pinned.innerHTML = ''
    const nodes = data.nodes || {}
    if (!Object.keys(nodes).length) {
      const empty = document.createElement('div')
      empty.className = 'kn-empty'
      empty.textContent = '(no pinned nodes yet)'
      pinned.appendChild(empty)
    }
    for (const [name, info] of Object.entries(nodes)) {
      const row = document.createElement('div')
      row.className = 'kn-row'
      row.dataset.service = name
      const nid = info.node_id || ''
      const label = document.createElement('span')
      label.textContent = `${name} — ${nid.slice(0, 8)} (${info.host_seen || info.host || ''})`
      row.appendChild(label)
      const addBtn = document.createElement('button')
      addBtn.type = 'button'
      addBtn.textContent = 'Use in allowlist'
      addBtn.addEventListener('click', () => {
        const inp = document.getElementById('ac-trusted_node_ids')
        if (!inp) return
        const cur = (inp.value || '').split(',').map(s => s.trim()).filter(Boolean)
        if (!cur.includes(nid)) cur.push(nid)
        inp.value = cur.join(',')
        inp.dispatchEvent(new Event('change', { bubbles: true }))
      })
      row.appendChild(addBtn)
      pinned.appendChild(row)
    }
  }
  if (rej) {
    rej.innerHTML = ''
    const rows = data.rejected || []
    if (!rows.length) {
      const empty = document.createElement('div')
      empty.className = 'kn-empty'
      empty.textContent = '(no pending rejections)'
      rej.appendChild(empty)
    }
    for (const row of rows) {
      const node = document.createElement('div')
      node.className = 'kn-rejection-row'
      const expected = (row.expected_node_id || '').slice(0, 8)
      const seen = (row.node_id || '').slice(0, 8)
      const text = document.createElement('div')
      text.textContent = `${row.service_name} — expected ${expected}, seen ${seen} from ${row.host_seen || ''}`
      node.appendChild(text)
      const attest = document.createElement('button')
      attest.type = 'button'
      attest.textContent = 'Attest'
      attest.addEventListener('click', async () => {
        await fetch('/api/admin/known-nodes/attest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service: row.service_name, node_id: row.node_id, host: row.host_seen || '' }),
        })
        loadKnownNodes()
      })
      node.appendChild(attest)
      const forget = document.createElement('button')
      forget.type = 'button'
      forget.textContent = 'Forget'
      forget.addEventListener('click', async () => {
        await fetch('/api/admin/known-nodes/forget', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service: row.service_name }),
        })
        loadKnownNodes()
      })
      node.appendChild(forget)
      rej.appendChild(node)
    }
  }
}

document.getElementById('kn-refresh')?.addEventListener('click', loadKnownNodes)

if (document.getElementById('kn-pinned-list') || document.getElementById('kn-rejections-list')) {
  loadKnownNodes()
}
