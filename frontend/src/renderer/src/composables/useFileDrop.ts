import { ref, onMounted, onUnmounted, type Ref } from 'vue'

interface UseFileDropOptions {
  isUploading: Ref<boolean> | (() => boolean)
  isAllowed?: (fileName: string) => boolean
  onUpload: (file: File) => Promise<unknown> | unknown
  onError?: (message: string) => void
}

export function useFileDrop(options: UseFileDropOptions) {
  const showOverlay = ref(false)
  let dragCounter = 0
  let leaveTimer: ReturnType<typeof setTimeout> | null = null

  const getUploading = () => {
    const { isUploading } = options
    return typeof isUploading === 'function' ? isUploading() : isUploading.value
  }

  const reportError = (message: string) => {
    options.onError?.(message)
  }

  const resetOverlay = () => {
    if (leaveTimer) {
      clearTimeout(leaveTimer)
      leaveTimer = null
    }
    showOverlay.value = false
    dragCounter = 0
  }

  const handleDragEnter = (e: DragEvent) => {
    if (e.dataTransfer?.types.includes('Files')) {
      e.preventDefault()
      if (leaveTimer) {
        clearTimeout(leaveTimer)
        leaveTimer = null
      }
      dragCounter++
      showOverlay.value = true
    }
  }

  const handleDragOver = (e: DragEvent) => {
    if (e.dataTransfer?.types.includes('Files')) {
      e.preventDefault()
      if (leaveTimer) {
        clearTimeout(leaveTimer)
        leaveTimer = null
      }
      showOverlay.value = true
    }
  }

  const handleDragLeave = (e: DragEvent) => {
    if (e.dataTransfer?.types.includes('Files')) {
      e.preventDefault()
      dragCounter--
      if (dragCounter <= 0) {
        leaveTimer = setTimeout(() => {
          showOverlay.value = false
          dragCounter = 0
        }, 100)
      }
    }
  }

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault()
    resetOverlay()
    if (getUploading()) return

    const files = e.dataTransfer?.files
    if (!files || files.length === 0) return

    const file = files[0]
    if (options.isAllowed && !options.isAllowed(file.name)) {
      reportError(`不支持的文件类型: ${file.name}`)
      return
    }
    await options.onUpload(file)
  }

  const handlePaste = async (e: ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === 'file') {
        const file = items[i].getAsFile()
        if (!file) continue
        if (getUploading()) return
        if (options.isAllowed && !options.isAllowed(file.name)) {
          reportError(`不支持的文件类型: ${file.name}`)
          continue
        }
        e.preventDefault()
        await options.onUpload(file)
        return
      }
    }
  }

  onMounted(() => {
    document.addEventListener('dragenter', handleDragEnter)
    document.addEventListener('dragover', handleDragOver)
    document.addEventListener('dragleave', handleDragLeave)
    document.addEventListener('drop', handleDrop)
    document.addEventListener('paste', handlePaste)
  })

  onUnmounted(() => {
    document.removeEventListener('dragenter', handleDragEnter)
    document.removeEventListener('dragover', handleDragOver)
    document.removeEventListener('dragleave', handleDragLeave)
    document.removeEventListener('drop', handleDrop)
    document.removeEventListener('paste', handlePaste)
    resetOverlay()
  })

  return {
    showOverlay,
  }
}
