import { session } from 'electron'

interface CdpConnection {
  targetId: string
  url: string
  title: string
}

const connections = new Map<string, CdpConnection>()

export async function connectToTarget(targetId: string): Promise<CdpConnection> {
  const ses = session.defaultSession
  const debugTargets = await ses.getDebugTargets()

  const target = debugTargets.find(t => t.id === targetId)
  if (!target) throw new Error(`CDP target ${targetId} not found`)

  const conn: CdpConnection = {
    targetId,
    url: target.title || '',
    title: target.title || ''
  }

  connections.set(targetId, conn)
  return conn
}

export async function listCdpTargets(): Promise<CdpConnection[]> {
  const ses = session.defaultSession
  const targets = await ses.getDebugTargets()
  return targets.map(t => ({
    targetId: t.id,
    url: t.title || '',
    title: t.title || ''
  }))
}

export async function sendCdpCommand(targetId: string, method: string, params?: Record<string, any>): Promise<any> {
  const ses = session.defaultSession
  try {
    const result = await ses.sendCDPCommand(method as any, params || {})
    return result
  } catch (err) {
    console.error(`CDP command failed: ${method}`, err)
    throw err
  }
}

export async function disconnectTarget(targetId: string): Promise<void> {
  connections.delete(targetId)
}
