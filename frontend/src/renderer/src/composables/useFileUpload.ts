import { ref } from 'vue'
import { API_ENDPOINTS } from '../config/api'

const uploadingFile = ref<{ name: string; status: 'uploading' | 'success' | 'failed'; type?: string; result?: string; error?: string } | null>(null)
const isUploading = ref(false)
const parsedContent = ref('')
const fileType = ref('')
const fileName = ref('')
let currentUploadController: AbortController | null = null

export function useFileUpload() {
  const uploadAndForward = async (file: File): Promise<string> => {
    if (currentUploadController) {
      currentUploadController.abort()
    }
    currentUploadController = new AbortController()

    uploadingFile.value = { name: file.name, status: 'uploading' }
    isUploading.value = true
    parsedContent.value = ''
    fileType.value = ''

    try {
      const formData = new FormData()
      formData.append('file', file)

      const token = await window.api.auth.getToken()
      const resp = await fetch(API_ENDPOINTS.UPLOAD_FORWARD, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        signal: currentUploadController.signal,
      })

      const data = await resp.json()

      if (!resp.ok || data.code !== 0) {
        const errMsg = data?.message || data?.error?.message || '上传失败'
        uploadingFile.value = { name: file.name, status: 'failed', error: errMsg }
        isUploading.value = false
        currentUploadController = null
        return ''
      }

      const payload = data.data || {}
      const content = payload.content || ''
      parsedContent.value = content
      fileType.value = payload.type || 'text'
      fileName.value = file.name
      uploadingFile.value = { name: file.name, status: 'success', type: payload.type, result: content }
      isUploading.value = false
      currentUploadController = null
      return content
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        return ''
      }
      uploadingFile.value = { name: file.name, status: 'failed', error: '网络错误，请检查后端服务' }
      isUploading.value = false
      currentUploadController = null
      return ''
    }
  }

  const clearUploadState = () => {
    if (currentUploadController) {
      currentUploadController.abort()
      currentUploadController = null
    }
    isUploading.value = false
    uploadingFile.value = null
    parsedContent.value = ''
    fileType.value = ''
    fileName.value = ''
  }

  return {
    uploadingFile,
    isUploading,
    parsedContent,
    fileType,
    fileName,
    uploadAndForward,
    clearUploadState,
  }
}