import type { Component } from 'vue'
import { FileText, Image, File } from 'lucide-vue-next'

export const ALLOWED_UPLOAD_EXTENSIONS = [
  '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
  '.pdf', '.docx', '.doc', '.txt', '.md', '.csv',
  '.json', '.xml', '.html', '.css', '.js', '.py',
  '.java', '.cpp', '.c', '.h', '.go', '.rs', '.ts',
  '.sql', '.yaml', '.yml',
] as const

export const ACCEPT_UPLOAD_EXTENSIONS = ALLOWED_UPLOAD_EXTENSIONS.join(',')

export const isUploadAllowed = (fileName: string): boolean => {
  const ext = fileName.toLowerCase().substring(fileName.lastIndexOf('.'))
  return ALLOWED_UPLOAD_EXTENSIONS.includes(ext as typeof ALLOWED_UPLOAD_EXTENSIONS[number])
}

const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
const TEXT_EXTENSIONS = ['txt', 'md', 'json', 'xml', 'csv']

export const getFileIcon = (fileName: string): Component => {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  if (IMAGE_EXTENSIONS.includes(ext)) return Image
  if (TEXT_EXTENSIONS.includes(ext)) return FileText
  return File
}
