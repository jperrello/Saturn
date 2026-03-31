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

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
    tab.classList.add('active')
    document.getElementById(tab.dataset.tab).classList.add('active')
  })
})

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

window.addEventListener('load', () => {
  setTimeout(initSaturn, 100)
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

loadServices()

// admin password gate for service configuration
let adminUnlocked = sessionStorage.getItem('saturn-admin') === '1'

function showAdminState() {
  document.getElementById('admin-gate').classList.toggle('hidden', adminUnlocked)
  document.getElementById('admin-prompt').classList.add('hidden')
  document.getElementById('config-btn').classList.toggle('hidden', !adminUnlocked)
}
showAdminState()

document.getElementById('admin-unlock').addEventListener('click', () => {
  document.getElementById('admin-gate').classList.add('hidden')
  document.getElementById('admin-prompt').classList.remove('hidden')
  document.getElementById('admin-pw').focus()
})

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
      let toolHTML = ''
      if (m.toolCalls && m.toolCalls.length > 0) {
        const badges = m.toolCalls.map(tc => {
          let args = {}
          try { args = JSON.parse(tc.arguments) } catch { args = {} }
          return renderToolCallBadge(tc.name, args)
        }).join(' ')
        toolHTML = `<div class="tool-calls-row">${badges}</div>`
      }
      const metaLabel = m.routedBy === 'brutus'
        ? `brutus → ${m.service || ''} // ${m.model || ''}`
        : `${m.service || ''} // ${m.model || ''}`
      div.innerHTML = `
        <div class="meta">${metaLabel}</div>
        <div class="bubble markdown-body">${toolHTML}${renderWithThinking(m.text)}</div>
      `
    }
    messagesEl.appendChild(div)
  })
  highlightCode(messagesEl)
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
  if (chats.length > MAX_CHATS) chats.length = MAX_CHATS
  saveChats()
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
  sendBtn.disabled = true

  let actualService = service, actualModel = model

  try {
    const endpoint = isBrutus ? '/api/brutus/chat' : '/api/chat'
    const payload = isBrutus
      ? { messages: apiMessages }
      : { service, model, messages: apiMessages, ...getActiveParams() }

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      full = `[error] ${err.error || res.statusText}`
      bubble.innerHTML = esc(full)
      chat.messages.push({ role: 'assistant', text: full, service: actualService, model: actualModel })
      saveChats()
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
          const delta = chunk.choices?.[0]?.delta
          if (delta?.content) {
            full += delta.content
            const parts = splitThinking(full)
            if (parts.pending) {
              bubble.innerHTML = renderThinkingHTML(parts.thinking) + '<span class="cursor">▊</span>'
            } else {
              bubble.innerHTML = renderThinkingHTML(parts.thinking) + renderMarkdown(parts.body) + '<span class="cursor">▊</span>'
            }
            messagesEl.scrollTop = messagesEl.scrollHeight
          }
          if (delta?.tool_calls) {
            for (const tc of delta.tool_calls) {
              const idx = tc.index ?? toolCalls.length
              if (!toolCalls[idx]) toolCalls[idx] = { name: '', arguments: '' }
              if (tc.function?.name) toolCalls[idx].name = tc.function.name
              if (tc.function?.arguments) toolCalls[idx].arguments += tc.function.arguments
            }
          }
        } catch {
          // skip malformed chunks
        }
      }
    }

    // render tool call badges if present
    let toolHTML = ''
    if (toolCalls.length > 0) {
      const badges = toolCalls.map(tc => {
        let args = {}
        try { args = JSON.parse(tc.arguments) } catch { /* partial args */ }
        return renderToolCallBadge(tc.name, args)
      }).join(' ')
      toolHTML = `<div class="tool-calls-row">${badges}</div>`
    }

    // remove cursor, finalize
    bubble.innerHTML = toolHTML + renderWithThinking(full)
    highlightCode(bubble)
    chat.messages.push({
      role: 'assistant', text: full || '[empty response]',
      service: actualService, model: actualModel,
      routedBy: isBrutus ? 'brutus' : undefined,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
    })
    saveChats()
  } catch (e) {
    full = `[error] ${e.message}`
    bubble.innerHTML = esc(full)
    chat.messages.push({ role: 'assistant', text: full, service: actualService, model: actualModel })
    saveChats()
  } finally {
    sending = false
    sendBtn.disabled = false
  }
}

document.getElementById('new-chat-btn').addEventListener('click', newChat)
document.getElementById('clear-chats-btn').addEventListener('click', () => {
  chats.length = 0
  activeChat = null
  saveChats()
  renderHistory()
  renderMessages()
})
sendBtn.addEventListener('click', send)
input.addEventListener('keydown', e => { if (e.key === 'Enter') send() })

document.querySelectorAll('.example').forEach(ex => {
  ex.addEventListener('click', () => {
    input.value = ex.textContent
    send()
  })
})

renderHistory()
renderMessages()

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
  }
})

// start/stop auto-refresh based on tab visibility
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'brutus') {
      if (!_brutusRefreshTimer) {
        _brutusRefreshTimer = setInterval(loadBrutusStatus, 5000)
      }
    } else if (_brutusRefreshTimer) {
      clearInterval(_brutusRefreshTimer)
      _brutusRefreshTimer = null
    }
  })
})
