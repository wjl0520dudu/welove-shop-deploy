/**
 * H5 端 SSE 传输层
 *
 * 浏览器原生 EventSource 只支持 GET、且无法自定义请求头/请求体，
 * 无法携带 Authorization 与 JSON body，故这里用 fetch + ReadableStream 手工解析 SSE 帧。
 * 仅面向 H5（依赖 fetch / ReadableStream / TextDecoder）。
 *
 * @param {string} url  请求地址（相对 /api，交由代理/同源转发）
 * @param {object} opts
 * @param {object} [opts.headers]        额外请求头（如 Authorization）
 * @param {any}    [opts.body]           请求体，对象自动 JSON 序列化
 * @param {(res:Response)=>void} [opts.onOpen]   连接建立回调
 * @param {(evt:{event:string,data:string})=>void} [opts.onEvent] 解析出的每一帧
 * @param {number} [opts.idleTimeoutMs]  无数据静默超时（毫秒），超时中止
 * @returns {{ promise: Promise<void>, abort: () => void }}
 */
export function postEventStream(url, {
  headers = {},
  body = null,
  onOpen,
  onEvent,
  idleTimeoutMs = 60000
} = {}) {
  const controller = new AbortController()
  let idleTimer = null

  const clearIdle = () => { if (idleTimer) { clearTimeout(idleTimer); idleTimer = null } }
  const armIdle = () => {
    clearIdle()
    if (idleTimeoutMs > 0) {
      idleTimer = setTimeout(() => controller.abort(), idleTimeoutMs)
    }
  }

  // 解析单个 SSE 帧：event: 行取事件名，data: 行拼接为数据（去掉一个前导空格），冒号开头为注释/心跳
  const dispatchFrame = (frame) => {
    if (!frame) return
    let event = 'message'
    const dataLines = []
    for (const line of frame.split(/\r?\n/)) {
      if (!line || line.startsWith(':')) continue
      const idx = line.indexOf(':')
      const field = idx === -1 ? line : line.slice(0, idx)
      let value = idx === -1 ? '' : line.slice(idx + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') dataLines.push(value)
    }
    if (dataLines.length && onEvent) {
      onEvent({ event, data: dataLines.join('\n') })
    }
  }

  const run = async () => {
    const res = await fetch(url, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...headers
      },
      body: body == null ? undefined : (typeof body === 'string' ? body : JSON.stringify(body))
    })

    if (!res.ok) {
      throw Object.assign(new Error(`SSE HTTP ${res.status}`), { status: res.status })
    }
    if (!res.body || typeof res.body.getReader !== 'function') {
      throw Object.assign(new Error('ReadableStream unsupported'), { code: 'NO_STREAM' })
    }
    if (onOpen) onOpen(res)

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    armIdle()

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        armIdle()
        // stream:true 保证中文多字节序列跨 chunk 时不会被截断
        buf += decoder.decode(value, { stream: true })
        let sep
        while ((sep = buf.match(/\r?\n\r?\n/))) {
          const frame = buf.slice(0, sep.index)
          buf = buf.slice(sep.index + sep[0].length)
          dispatchFrame(frame)
        }
      }
      buf += decoder.decode()
      if (buf.trim()) dispatchFrame(buf)
    } finally {
      clearIdle()
    }
  }

  const promise = run().finally(clearIdle)
  return { promise, abort: () => controller.abort() }
}

/** 当前 H5 运行环境是否支持流式（fetch + ReadableStream） */
export function supportsEventStream() {
  return typeof fetch === 'function' &&
    typeof ReadableStream === 'function' &&
    typeof TextDecoder === 'function'
}
