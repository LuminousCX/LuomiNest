const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('homeApi', {
  search: (url) => ipcRenderer.invoke('home:search', url),
  action: (action) => ipcRenderer.invoke('home:action', action)
})
