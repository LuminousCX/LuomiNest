import { app } from 'electron'
import { join } from 'path'
import { mkdirSync } from 'fs'

const APP_NAME = 'LuomiNest'

const ensureDir = (dir: string): string => {
  mkdirSync(dir, { recursive: true })
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
    return app.getPath('cache')
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

  console.info(`[INFO][${APP_NAME}Paths] userData: ${PATHS.userData}`)
  console.info(`[INFO][${APP_NAME}Paths] cache: ${PATHS.cache}`)
  console.info(`[INFO][${APP_NAME}Paths] data: ${PATHS.data}`)
  console.info(`[INFO][${APP_NAME}Paths] config: ${PATHS.config}`)
  console.info(`[INFO][${APP_NAME}Paths] logs: ${PATHS.logs}`)
}
