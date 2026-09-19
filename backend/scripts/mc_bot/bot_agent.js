/**
 * LuomiNest Minecraft Embodied AI Companion Bot
 * 
 * 基于 Mineflayer 实现的原生虚拟玩家实体：
 * 1. 作为玩家实体加入局域网单人游戏 (例如端口 56587) 或多人服务器；
 * 2. 桥接连接 LuomiNest 平台的 WebSocket 端点 (例如 ws://127.0.0.1:8081)；
 * 3. 实时上报自身环境遥测 (坐标、生命值、注视方块、附近实体)；
 * 4. 监听游戏公屏聊天，转发给 LuomiNest 主 Agent / DeepSeek；
 * 5. 接收 LuomiNest 下发的具身指令并在游戏内执行 (打字说话、攻击、跟随移动、挖掘)。
 */

const mineflayer = require('./node_modules/mineflayer')

const args = process.argv.slice(2)
function getArg(key, def) {
  const idx = args.indexOf(key)
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : def
}

const gameHost = getArg('--host', '127.0.0.1')
const gamePort = parseInt(getArg('--port', '56587'), 10)
const wsPort = parseInt(getArg('--ws-port', '8081'), 10)
const botName = getArg('--name', 'LuomiNest')
const mcVersion = getArg('--version', '1.21.1')

console.log(`[MC-Bot] 准备启动虚拟玩家伴侣: ${botName}`)
console.log(`[MC-Bot] 目标游戏地址: ${gameHost}:${gamePort} (MC版本: ${mcVersion})`)
console.log(`[MC-Bot] 目标 LuomiNest WS 端口: ${wsPort}`)

let bot = null
let ws = null
let telemetryTimer = null
let isShuttingDown = false

function connectToWebSocket() {
  if (isShuttingDown) return
  const wsUrl = `ws://127.0.0.1:${wsPort}`
  console.log(`[MC-Bot] 正在连接 LuomiNest 大脑端点: ${wsUrl}...`)

  try {
    ws = new WebSocket(wsUrl)
  } catch (err) {
    console.error(`[MC-Bot] 创建 WebSocket 客户端失败:`, err.message)
    setTimeout(connectToWebSocket, 3000)
    return
  }

  ws.onopen = () => {
    console.log(`[MC-Bot] ✅ 成功连接到 LuomiNest 大脑通道 (ws://127.0.0.1:${wsPort})！`)
    sendTelemetry()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleLuomiNestCommand(data)
    } catch (e) {
      console.warn(`[MC-Bot] 解析 LuomiNest 消息失败:`, e.message)
    }
  }

  ws.onerror = (err) => {
    console.warn(`[MC-Bot] WS 通道异常:`, err.message || '连接错误')
  }

  ws.onclose = () => {
    console.log(`[MC-Bot] WS 通道已断开，3 秒后重试...`)
    ws = null
    if (!isShuttingDown) {
      setTimeout(connectToWebSocket, 3000)
    }
  }
}

function handleLuomiNestCommand(data) {
  if (!bot) return
  const actionType = data.action || data.type
  const params = data.params || {}
  const actionId = data.action_id || data.echo

  console.log(`[MC-Bot] 收到大模型具身指令:`, actionType, params)

  let success = false
  let resultMsg = ''

  try {
    if (actionType === 'say') {
      const msg = params.message || params.content || data.content || ''
      if (msg) {
        bot.chat(msg)
        success = true
        resultMsg = `已在公屏说话: ${msg}`
      }
    } else if (actionType === 'navigate') {
      const x = params.x ?? (bot.entity ? bot.entity.position.x : 0)
      const y = params.y ?? (bot.entity ? bot.entity.position.y : 0)
      const z = params.z ?? (bot.entity ? bot.entity.position.z : 0)
      if (bot.entity) {
        bot.lookAt({ x, y: y + 1.6, z })
        bot.setControlState('forward', true)
        setTimeout(() => {
          if (bot) bot.setControlState('forward', false)
        }, 2000)
        success = true
        resultMsg = `朝目标 [${x.toFixed(1)}, ${y.toFixed(1)}, ${z.toFixed(1)}] 移动中`
      }
    } else if (actionType === 'attack') {
      const targetName = params.target || 'zombie'
      const entity = bot.nearestEntity((e) => e.name && e.name.toLowerCase().includes(targetName.toLowerCase()))
      if (entity) {
        bot.attack(entity)
        success = true
        resultMsg = `已攻击目标 ${entity.name}`
      } else {
        resultMsg = `未在附近找到目标 ${targetName}`
      }
    } else if (actionType === 'jump') {
      bot.setControlState('jump', true)
      setTimeout(() => { if (bot) bot.setControlState('jump', false) }, 500)
      success = true
      resultMsg = '已跳跃'
    } else if (actionType === 'look_at') {
      if (params.x !== undefined && params.y !== undefined && params.z !== undefined) {
        bot.lookAt({ x: params.x, y: params.y, z: params.z })
        success = true
        resultMsg = '已转动视角'
      }
    } else {
      resultMsg = `未实现的动作: ${actionType}`
    }
  } catch (err) {
    resultMsg = `动作执行异常: ${err.message}`
  }

  // 回传动作执行回执
  if (actionId && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      action_id: actionId,
      echo: actionId,
      success,
      message: resultMsg,
      timestamp: Date.now() / 1000
    }))
  }
}

function sendTelemetry() {
  if (!bot || !bot.entity || !ws || ws.readyState !== WebSocket.OPEN) return

  try {
    const pos = bot.entity.position
    const nearby = []
    for (const id in bot.entities) {
      const e = bot.entities[id]
      if (e && e !== bot.entity && e.position) {
        const dist = bot.entity.position.distanceTo(e.position)
        if (dist <= 16 && (e.name || e.username)) {
          nearby.push({
            name: e.username || e.name,
            type: e.type,
            distance: parseFloat(dist.toFixed(1)),
            position: [parseFloat(e.position.x.toFixed(1)), parseFloat(e.position.y.toFixed(1)), parseFloat(e.position.z.toFixed(1))]
          })
        }
      }
    }

    const lookingAtBlock = bot.blockAtCursor(5)

    const telemetry = {
      type: 'telemetry',
      player: bot.username,
      dimension: bot.game ? bot.game.dimension : 'minecraft:overworld',
      position: [parseFloat(pos.x.toFixed(1)), parseFloat(pos.y.toFixed(1)), parseFloat(pos.z.toFixed(1))],
      health: bot.health || 20,
      hunger: bot.food || 20,
      looking_at: lookingAtBlock ? {
        block: lookingAtBlock.name,
        x: lookingAtBlock.position.x,
        y: lookingAtBlock.position.y,
        z: lookingAtBlock.position.z,
      } : null,
      nearby_entities: nearby.slice(0, 10),
      timestamp: Date.now() / 1000,
    }

    ws.send(JSON.stringify(telemetry))
  } catch (err) {
    // 忽略遥测收集微小异常
  }
}

function createBot() {
  if (isShuttingDown) return
  console.log(`[MC-Bot] 正在向游戏发送登录联机请求: ${gameHost}:${gamePort}...`)

  try {
    bot = mineflayer.createBot({
      host: gameHost,
      port: gamePort,
      username: botName,
      version: false, // 自动协商版本 (自适应 1.21.1)
      hideErrors: false,
      checkTimeoutInterval: 60 * 1000,
    })
  } catch (err) {
    console.error(`[MC-Bot] 创建 Mineflayer 实例失败:`, err.message)
    setTimeout(createBot, 5000)
    return
  }

  bot.on('login', () => {
    console.log(`[MC-Bot] 🎮 登录协议握手成功！`)
  })

  bot.on('spawn', () => {
    console.log(`[MC-Bot] 🎉 【实体成功降临游戏世界】！`)
    console.log(`[MC-Bot] 角色名: ${bot.username}, 坐标: ${bot.entity.position}`)

    // 进服打招呼
    setTimeout(() => {
      try {
        bot.chat(`你好！我是 AI 伴侣 ${bot.username}，已成功降临你的世界！`)
      } catch {}
    }, 1500)

    // 定期遥测
    if (telemetryTimer) clearInterval(telemetryTimer)
    telemetryTimer = setInterval(sendTelemetry, 3000)
  })

  bot.on('chat', (username, message) => {
    if (username === bot.username) return
    console.log(`[MC-Bot] 收到玩家聊天 <${username}>: ${message}`)

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'chat',
        player: username,
        content: message,
        timestamp: Date.now() / 1000,
      }))
    }
  })

  bot.on('kicked', (reason) => {
    console.warn(`[MC-Bot] 被服务器踢出:`, reason)
  })

  bot.on('error', (err) => {
    console.error(`[MC-Bot] 客户端网络异常:`, err.message)
  })

  bot.on('end', () => {
    console.log(`[MC-Bot] 游戏连接已关闭`)
    if (telemetryTimer) {
      clearInterval(telemetryTimer)
      telemetryTimer = null
    }
    bot = null
    if (!isShuttingDown) {
      console.log(`[MC-Bot] 5 秒后尝试重连游戏...`)
      setTimeout(createBot, 5000)
    }
  })
}

// 启动连接
connectToWebSocket()
createBot()

// 进程平滑退出清理
process.on('SIGINT', () => {
  isShuttingDown = true
  console.log(`[MC-Bot] 正在退出...`)
  if (telemetryTimer) clearInterval(telemetryTimer)
  if (bot) try { bot.quit() } catch {}
  if (ws) try { ws.close() } catch {}
  process.exit(0)
})

process.on('SIGTERM', () => {
  isShuttingDown = true
  if (telemetryTimer) clearInterval(telemetryTimer)
  if (bot) try { bot.quit() } catch {}
  if (ws) try { ws.close() } catch {}
  process.exit(0)
})
