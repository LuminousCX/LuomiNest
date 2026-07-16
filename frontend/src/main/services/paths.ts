import { app } from 'electron'
import { join } from 'path'
import { mkdirSync } from 'fs'
import { createLuomiNestLogger } from './luomi-logger'

const logger = createLuomiNestLogger('Paths')

const APP_NAME = 'LuomiNest'

const createdDirs = new Set<string>()

const ensureDir = (dir: string): string => {
  if (!createdDirs.has(dir)) {
    mkdirSync(dir, { recursive: true })
    createdDirs.add(dir)
  }
  return dir
}

export const PATHS = {
  get userData() {
    return app.getPath('userData')
  },
  get appData() {
    return app.getPath('appData')
  },
  get cache() {
    return ensureDir(join(app.getPath('userData'), 'Cache'))
  },
  get logs() {
    return ensureDir(join(app.getPath('userData'), 'Logs'))
  },
  get config() {
    return ensureDir(join(this.userData, 'Config'))
  },
  get data() {
    return ensureDir(join(this.userData, 'Data'))
  },
  get live2d() {
    return ensureDir(join(this.userData, 'live2d'))
  },
  get avatar() {
    // 多模型统一目录：userData/avatar/{live2d|vrm|pixel|spine|png}/
    return ensureDir(join(this.userData, 'avatar'))
  },
  get live2dCache() {
    return ensureDir(join(this.cache, 'live2d'))
  },
  get ttsCache() {
    return ensureDir(join(this.cache, 'tts'))
  },
  get imageCache() {
    return ensureDir(join(this.cache, 'images'))
  },
  get sessions() {
    return ensureDir(join(this.data, 'sessions'))
  },
  get memory() {
    return ensureDir(join(this.data, 'memory'))
  },
  get backendData() {
    return ensureDir(join(this.data, 'backend'))
  },
  get configFilePath() {
    return join(this.config, 'config.json')
  },
  get windowStatePath() {
    return join(this.config, 'window-state.json')
  },
  get importedModelsPath() {
    return join(this.live2d, 'imported-models.json')
  },
} as const

export const initAppPaths = (): void => {
  app.setAppLogsPath(PATHS.logs)

  logger.info(`userData: ${PATHS.userData}`)
  logger.info(`cache: ${PATHS.cache}`)
  logger.info(`data: ${PATHS.data}`)
  logger.info(`config: ${PATHS.config}`)
  logger.info(`logs: ${PATHS.logs}`)
}
