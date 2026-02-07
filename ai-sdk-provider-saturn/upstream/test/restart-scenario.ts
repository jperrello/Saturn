#!/usr/bin/env npx tsx
/**
 * Saturn SDK Restart Scenario Test
 * 
 * Tests whether the SDK correctly handles service restarts and late discovery.
 * This determines if bugs are in the SDK itself or in OpenCode's integration.
 * 
 * Run: npx tsx test/restart-scenario.ts
 */

import { spawn, ChildProcess } from 'node:child_process'
import { createSaturn, DiscoveredService, SaturnProvider } from '../src/index.js'
import { generateText } from 'ai'

let portCounter = 18780
function getNextPort(): number {
  return portCounter++
}

type TestResult = 'pass' | 'fail' | 'skip'

interface PhaseResult {
  name: string
  result: TestResult
  error?: string
  details?: Record<string, unknown>
}

function log(msg: string, data?: Record<string, unknown>) {
  const ts = new Date().toISOString().slice(11, 23)
  if (data) {
    console.log(`[${ts}] ${msg}`, JSON.stringify(data))
  } else {
    console.log(`[${ts}] ${msg}`)
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

interface ServerHandle {
  proc: ChildProcess
  port: number
  name: string
}

async function startMockServer(name: string): Promise<ServerHandle> {
  const port = getNextPort()
  log('Starting mock server...', { port, name })
  
  const proc = spawn('npx', [
    'tsx', 'src/mock-server.ts',
    '--port', String(port),
    '--name', name,
    '--priority', '10',
    '--rotation', '300'
  ], {
    cwd: process.cwd(),
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: true
  })

  proc.stdout?.on('data', (data) => {
    const line = data.toString().trim()
    if (line) log(`[${name}] ${line}`)
  })
  
  proc.stderr?.on('data', (data) => {
    const line = data.toString().trim()
    if (line && !line.includes('ExperimentalWarning')) log(`[${name}:err] ${line}`)
  })

  await sleep(2500)
  return { proc, port, name }
}

async function stopMockServer(handle: ServerHandle): Promise<void> {
  return new Promise(resolve => {
    log('Stopping mock server...', { name: handle.name })
    
    const timeout = setTimeout(() => {
      if (!handle.proc.killed) {
        handle.proc.kill('SIGKILL')
      }
      resolve()
    }, 5000)
    
    handle.proc.on('exit', () => {
      clearTimeout(timeout)
      log('Mock server stopped', { name: handle.name })
      resolve()
    })
    
    handle.proc.kill('SIGTERM')
  })
}

async function makeInference(saturn: SaturnProvider, model: string): Promise<{ success: boolean, response?: string, error?: string }> {
  try {
    log('Making inference request...', { model })
    
    const result = await generateText({
      model: saturn(model),
      prompt: 'Hello, how are you today?'
    })

    log('Inference successful', { 
      responseLength: result.text.length,
      preview: result.text.slice(0, 50)
    })
    
    return { success: true, response: result.text }
  } catch (err) {
    const msg = (err as Error).message
    log('Inference failed', { error: msg })
    return { success: false, error: msg }
  }
}

async function waitForService(saturn: SaturnProvider, serviceName: string, timeout: number): Promise<DiscoveredService | null> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const services = saturn.getDiscovery().getAllServices()
    const service = services.find(s => s.name === serviceName)
    if (service) return service
    await sleep(200)
  }
  return null
}

async function runPhase1(): Promise<PhaseResult> {
  log('\n=== PHASE 1: Initial Discovery ===')
  log('Testing: start service -> start SDK -> discover -> inference')
  
  const server = await startMockServer('Phase1Server')
  
  const saturn = createSaturn({
    logLevel: 'info',
    onServiceDiscovered: (service) => {
      log('Service discovered', { name: service.name, host: service.host, models: service.models })
    }
  })
  
  try {
    const service = await waitForService(saturn, 'Phase1Server', 5000)
    
    if (!service) {
      return { 
        name: 'Phase 1: Initial Discovery', 
        result: 'fail', 
        error: 'Service not discovered within timeout' 
      }
    }
    
    log('Target service found', { name: service.name, host: service.host, port: service.port })
    
    await saturn.getDiscovery().fetchAllModels()
    const inference = await makeInference(saturn, 'eliza')
    
    if (!inference.success) {
      return { 
        name: 'Phase 1: Initial Discovery', 
        result: 'fail', 
        error: `Inference failed: ${inference.error}`
      }
    }
    
    return { 
      name: 'Phase 1: Initial Discovery', 
      result: 'pass',
      details: { response: inference.response?.slice(0, 100) }
    }
  } finally {
    saturn.destroy()
    await stopMockServer(server)
    await sleep(1000)
  }
}

async function runPhase2(): Promise<PhaseResult> {
  log('\n=== PHASE 2: Service Restart ===')
  log('Testing: start service -> discover -> inference -> stop -> restart with NEW PORT -> re-discover -> inference')
  
  let removedServiceName: string | null = null
  let rediscoveredAt: number | null = null
  
  const saturn = createSaturn({
    logLevel: 'info',
    onServiceDiscovered: (service) => {
      if (service.name === 'Phase2Server') {
        log('Service discovered/re-discovered', { name: service.name, host: service.host })
        rediscoveredAt = Date.now()
      }
    },
    onServiceRemoved: (name) => {
      if (name === 'Phase2Server') {
        log('Service removal detected', { name })
        removedServiceName = name
      }
    }
  })
  
  let server1: ServerHandle | null = null
  let server2: ServerHandle | null = null
  
  try {
    server1 = await startMockServer('Phase2Server')
    
    const service1 = await waitForService(saturn, 'Phase2Server', 5000)
    if (!service1) {
      return { 
        name: 'Phase 2: Service Restart', 
        result: 'fail', 
        error: 'Initial service not discovered' 
      }
    }
    
    await saturn.getDiscovery().fetchAllModels()
    const inference1 = await makeInference(saturn, 'eliza')
    if (!inference1.success) {
      return { 
        name: 'Phase 2: Service Restart', 
        result: 'fail', 
        error: `First inference failed: ${inference1.error}` 
      }
    }
    
    log('First inference succeeded, now stopping server...')
    await stopMockServer(server1)
    server1 = null
    
    log('Waiting for SDK to detect removal (via goodbye packet or timeout)...')
    await sleep(3000)
    
    rediscoveredAt = null
    log('Starting server on NEW PORT (simulating restart)...')
    server2 = await startMockServer('Phase2Server')
    
    log('Waiting for re-discovery...')
    const service2 = await waitForService(saturn, 'Phase2Server', 10000)
    
    if (!service2) {
      return { 
        name: 'Phase 2: Service Restart', 
        result: 'fail', 
        error: 'Service not re-discovered after restart',
        details: { removedDetected: !!removedServiceName }
      }
    }
    
    log('Service re-discovered, fetching models and making inference...')
    await saturn.getDiscovery().fetchAllModels()
    const inference2 = await makeInference(saturn, 'eliza')
    
    if (!inference2.success) {
      return { 
        name: 'Phase 2: Service Restart', 
        result: 'fail', 
        error: `Inference after restart failed: ${inference2.error}`,
        details: { removedDetected: !!removedServiceName, newPort: server2.port }
      }
    }
    
    return { 
      name: 'Phase 2: Service Restart', 
      result: 'pass',
      details: { 
        removedDetected: !!removedServiceName,
        newPort: server2.port,
        response: inference2.response?.slice(0, 100)
      }
    }
  } finally {
    saturn.destroy()
    if (server1) await stopMockServer(server1)
    if (server2) await stopMockServer(server2)
    await sleep(1000)
  }
}

async function runPhase3(): Promise<PhaseResult> {
  log('\n=== PHASE 3: Late Start ===')
  log('Testing: start SDK first (no services) -> start service later -> discover -> inference')
  
  let discoveredService: DiscoveredService | null = null
  
  const saturn = createSaturn({
    logLevel: 'info',
    discoveryTimeout: 15000,
    onServiceDiscovered: (service) => {
      if (service.name === 'Phase3Server') {
        log('Late service discovered', { name: service.name, host: service.host })
        discoveredService = service
      }
    }
  })
  
  let server: ServerHandle | null = null
  
  try {
    await sleep(1000)
    
    const initialServices = saturn.getDiscovery().getAllServices()
    log('Services before starting mock', { count: initialServices.length })
    
    log('Now starting mock server AFTER SDK...')
    server = await startMockServer('Phase3Server')
    
    const service = await waitForService(saturn, 'Phase3Server', 10000)
    
    if (!service) {
      return { 
        name: 'Phase 3: Late Start', 
        result: 'fail', 
        error: 'Service not discovered when started after SDK',
        details: { discoveredViaCallback: !!discoveredService }
      }
    }
    
    log('Late-started service found, fetching models...')
    await saturn.getDiscovery().fetchAllModels()
    
    const inference = await makeInference(saturn, 'eliza')
    
    if (!inference.success) {
      return { 
        name: 'Phase 3: Late Start', 
        result: 'fail', 
        error: `Inference failed for late-started service: ${inference.error}`
      }
    }
    
    return { 
      name: 'Phase 3: Late Start', 
      result: 'pass',
      details: { response: inference.response?.slice(0, 100) }
    }
  } finally {
    saturn.destroy()
    if (server) await stopMockServer(server)
  }
}

async function main() {
  console.log('\n' + '='.repeat(60))
  console.log(' Saturn SDK Restart Scenario Test')
  console.log('='.repeat(60))
  console.log('\nThis test determines whether re-registration bugs are in')
  console.log('the SDK itself or in OpenCode\'s integration.\n')
  
  const results: PhaseResult[] = []
  
  try {
    const phase1Result = await runPhase1()
    results.push(phase1Result)
    
    if (phase1Result.result === 'pass') {
      const phase2Result = await runPhase2()
      results.push(phase2Result)
      
      const phase3Result = await runPhase3()
      results.push(phase3Result)
    } else {
      results.push({ name: 'Phase 2: Service Restart', result: 'skip', error: 'Skipped due to Phase 1 failure' })
      results.push({ name: 'Phase 3: Late Start', result: 'skip', error: 'Skipped due to Phase 1 failure' })
    }
  } catch (err) {
    log('Fatal error', { error: (err as Error).message, stack: (err as Error).stack })
  }
  
  console.log('\n' + '='.repeat(60))
  console.log(' TEST RESULTS')
  console.log('='.repeat(60))
  
  for (const r of results) {
    const icon = r.result === 'pass' ? '✓' : r.result === 'fail' ? '✗' : '○'
    console.log(`\n${icon} ${r.name}: ${r.result.toUpperCase()}`)
    if (r.error) console.log(`   Error: ${r.error}`)
    if (r.details) console.log(`   Details: ${JSON.stringify(r.details)}`)
  }
  
  const passed = results.filter(r => r.result === 'pass').length
  const failed = results.filter(r => r.result === 'fail').length
  const skipped = results.filter(r => r.result === 'skip').length
  
  console.log('\n' + '-'.repeat(60))
  console.log(`SUMMARY: ${passed} passed, ${failed} failed, ${skipped} skipped`)
  console.log('-'.repeat(60))
  
  console.log('\nINTERPRETATION:')
  if (passed === 3) {
    console.log('✓ All phases passed - Bug is in OpenCode integration, NOT the SDK')
  } else if (passed === 1 && results[0].result === 'pass') {
    console.log('✗ Phase 1 passes but Phase 2/3 fail - Bug is in SDK re-discovery logic')
  } else if (passed === 0) {
    console.log('✗ Phase 1 fails - SDK has fundamental issues with initial discovery')
  } else {
    console.log('? Mixed results - needs further investigation')
  }
  
  console.log('')
  process.exit(failed > 0 ? 1 : 0)
}

main()
