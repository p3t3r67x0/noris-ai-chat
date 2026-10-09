// Loopback-only production browser fixture. Never included in deployment images.
import http from 'node:http'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'

/** @param {string} name @param {number} fallback */
function port(name, fallback) {
  const value = Number(process.env[name] ?? fallback)
  if (!Number.isSafeInteger(value) || value < 1 || value > 65535) throw new Error(`Invalid fixture port: ${name}`)
  return value
}

const frontendPort = port('NORIS_E2E_FRONTEND_PORT', 8593)
const backendPort = port('NORIS_E2E_BACKEND_PORT', 8592)
const nodePort = port('NORIS_E2E_NUXT_PORT', frontendPort + 10)
let stopping = false
const child = spawn(process.execPath, ['.output/server/index.mjs'], {
  stdio: 'inherit',
  env: { ...process.env, PORT: String(nodePort), HOST: '127.0.0.1' },
})
const server = http.createServer((request, response) => {
  const upstream = http.request({
    host: '127.0.0.1', port: request.url?.startsWith('/api/') ? backendPort : nodePort,
    path: request.url, method: request.method, headers: request.headers,
  }, result => {
    response.writeHead(result.statusCode ?? 502, result.headers)
    result.on('error', () => response.destroy())
    result.pipe(response)
  })
  upstream.on('error', () => {
    if (response.headersSent) response.destroy()
    else { response.writeHead(502); response.end() }
  })
  request.on('aborted', () => upstream.destroy())
  response.on('close', () => upstream.destroy())
  request.pipe(upstream)
})

function stop() {
  stopping = true
  server.close()
  child.kill('SIGTERM')
  process.exit(0)
}
process.on('SIGINT', stop)
process.on('SIGTERM', stop)
child.on('error', () => { process.exit(1) })
child.on('exit', () => { if (!stopping) process.exit(1) })

let ready = false
for (let attempt = 0; attempt < 100; attempt++) {
  try {
    const response = await fetch(`http://127.0.0.1:${nodePort}/`, { signal: AbortSignal.timeout(300) })
    await response.body?.cancel()
    if (response.ok) { ready = true; break }
  }
  catch { /* Wait for the child server within a fixed startup budget. */ }
  await delay(100)
}
if (!ready) { child.kill('SIGTERM'); process.exit(1) }
server.listen(frontendPort, '127.0.0.1')
