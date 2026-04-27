import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, Conversation, ConversationListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'
import { useAvatarControlStore } from './avatar-control'
import {
  ALL_LUOMINEST_TOOLS,
  formatToolsForLLM,
  buildLuomiNestSystemPrompt
} from '../config/luominest-tools'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()
  const avatarControl = useAvatarControlStore()

  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConversation = ref<Record<string, Conversation | null>>({})
  const agentMessages = ref<Record<string, ChatMessage[]>>({})
  const agentStreaming = ref<Record<string, boolean>>({})
  const agentAbortControllers = ref<Record<string, AbortController>>({})
  const isBackendReady = ref(false)
  const agentStreamingContent = ref<Record<string, string>>({})
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)
  const pendingToolCalls = ref<Record<string, any[]>>({})
  const conversationMessagesCache = ref<Record<string, ChatMessage[]>>({})
  const isLoadingConversation = ref<boolean>(false)

  const isStreaming = computed(() => agentStreaming.value[activeAgentId.value] || false)
  
  const streamingContent = computed({
    get: () => agentStreamingContent.value[activeAgentId.value] || '',
    set: (value) => {
      if (activeAgentId.value) {
        agentStreamingContent.value[activeAgentId.value] = value
      }
    }
  })

  const activeAgentId = computed(() => agentStore.activeAgent?.id || '')

  const conversations = computed(() => agentConversations.value[activeAgentId.value] || [])
  
  const currentConversation = computed({
    get: () => agentCurrentConversation.value[activeAgentId.value] || null,
    set: (value) => {
      if (activeAgentId.value) {
        agentCurrentConversation.value = {
          ...agentCurrentConversation.value,
          [activeAgentId.value]: value
        }
      }
    }
  })

  const messages = computed({
    get: () => agentMessages.value[activeAgentId.value] || [],
    set: (value) => {
      if (activeAgentId.value) {
        agentMessages.value = {
          ...agentMessages.value,
          [activeAgentId.value]: value
        }
      }
    }
  })

  const currentMessages = computed(() => messages.value)

  const fetchConversations = async (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    try {
      const query = `?agent_id=${targetAgentId}`
      const convs = await apiGet<ConversationListItem[]>(`/chat/conversations${query}`)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: convs
      }
    } catch {
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: []
      }
    }
  }

  const loadConversation = async (convId: string) => {
    if (!activeAgentId.value) return

    const cached = conversationMessagesCache.value[convId]
    if (cached && cached.length > 0) {
      agentMessages.value = {
        ...agentMessages.value,
        [activeAgentId.value]: cached.map(m => ({ ...m }))
      }
    } else {
      agentMessages.value = {
        ...agentMessages.value,
        [activeAgentId.value]: []
      }
    }

    isLoadingConversation.value = true

    try {
      const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
      agentCurrentConversation.value = {
        ...agentCurrentConversation.value,
        [activeAgentId.value]: conv
      }
      const mappedMessages = (conv.messages || []).map((m: any) => ({
        id: m.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp || Date.now(),
        done: true,
      }))
      agentMessages.value = {
        ...agentMessages.value,
        [activeAgentId.value]: mappedMessages
      }
      conversationMessagesCache.value = {
        ...conversationMessagesCache.value,
        [convId]: mappedMessages
      }
    } catch (error) {
      if (!cached || cached.length === 0) {
        agentMessages.value = {
          ...agentMessages.value,
          [activeAgentId.value]: []
        }
      }
    } finally {
      isLoadingConversation.value = false
    }
  }

  const cacheConversationMessages = (convId: string) => {
    const msgs = agentMessages.value[activeAgentId.value]
    if (msgs && msgs.length > 0) {
      conversationMessagesCache.value = {
        ...conversationMessagesCache.value,
        [convId]: [...msgs]
      }
    }
  }

  const checkBackend = async () => {
    isBackendReady.value = await checkHealth()
    return isBackendReady.value
  }

  const createConversation = async (title?: string, agentId?: string, model?: string, provider?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return null
    
    const conv = await apiPost<Conversation>('/chat/conversations', {
      title: title || 'New Conversation',
      agent_id: targetAgentId,
      model,
      provider,
    })
    agentCurrentConversation.value = {
      ...agentCurrentConversation.value,
      [targetAgentId]: conv
    }
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: []
    }
    await fetchConversations(targetAgentId)
    return conv
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    await apiDelete(`/chat/conversations/${convId}`)
    const newCache = { ...conversationMessagesCache.value }
    delete newCache[convId]
    conversationMessagesCache.value = newCache
    if (agentCurrentConversation.value[targetAgentId]?.id === convId) {
      agentCurrentConversation.value = {
        ...agentCurrentConversation.value,
        [targetAgentId]: null
      }
      agentMessages.value = {
        ...agentMessages.value,
        [targetAgentId]: []
      }
    }
    await fetchConversations(targetAgentId)
  }

  const cancelCurrentRequest = (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    const controller = agentAbortControllers.value[targetAgentId]
    if (controller) {
      controller.abort()
      delete agentAbortControllers.value[targetAgentId]
    }
    
    agentStreaming.value[targetAgentId] = false
    const currentMsgs = agentMessages.value[targetAgentId] || []
    const lastIndex = currentMsgs.length - 1
    if (lastIndex >= 0 && currentMsgs[lastIndex]?.role === 'assistant' && !currentMsgs[lastIndex].done) {
      agentMessages.value = {
        ...agentMessages.value,
        [targetAgentId]: [...currentMsgs.slice(0, lastIndex), {
          ...currentMsgs[lastIndex],
          done: true,
          content: currentMsgs[lastIndex].content || '[已中断]'
        }]
      }
    }
    agentStreamingContent.value[targetAgentId] = ''
  }

  const executeToolCall = async (toolName: string, args: Record<string, any>): Promise<string> => {
    try {
      switch (toolName) {
        case 'avatar_set_emotion':
          await avatarControl.driveEmotion(args.emotion, args.intensity ?? 0.5)
          return `Emotion set to ${args.emotion} (intensity: ${args.intensity ?? 0.5})`

        case 'avatar_trigger_motion':
          await avatarControl.triggerMotion(args.group, args.index ?? 0)
          return `Motion "${args.group}[${args.index ?? 0}]" triggered`

        case 'avatar_trigger_expression':
          await avatarControl.triggerExpression(args.name)
          return `Expression "${args.name}" applied`

        case 'avatar_drive_pad_emotion':
          await avatarControl.drivePadEmotion(args.pleasure, args.arousal, args.dominance)
          return `PAD emotion set: P=${args.pleasure}, A=${args.arousal}, D=${args.dominance}`

        case 'avatar_lip_sync':
          await avatarControl.driveLipSync(args.value)
          return `Lip sync value set to ${args.value}`

        case 'avatar_set_param':
          await avatarControl.setCoreParam(args.param_id, args.value)
          return `Parameter ${args.param_id} set to ${args.value}`

        case 'avatar_set_position':
          await avatarControl.setModelPosition(args.x, args.y)
          return `Avatar position set to (${args.x}, ${args.y})`

        case 'avatar_set_scale':
          await avatarControl.setModelScale(args.scale)
          return `Avatar scale set to ${args.scale}`

        case 'avatar_get_capabilities':
          await avatarControl.getModelCapabilities()
          return JSON.stringify({
            motions: avatarControl.availableMotions,
            expressions: avatarControl.availableExpressions,
            modelName: avatarControl.currentModelName
          })

        case 'memory_save':
          return `Memory saved: [${args.category}] ${args.content}`

        case 'memory_search':
          return `Memory search results for: "${args.query}"`

        case 'skill_execute':
          return `Skill "${args.skill_name}" executed`

        case 'skill_list':
          return 'Available skills: (loaded from skill registry)'

        case 'mcp_call_tool':
          return `MCP tool "${args.tool_name}" called on server "${args.server_name}"`

        case 'mcp_list_servers':
          return 'Connected MCP servers: (loaded from MCP registry)'

        default:
          return `Unknown tool: ${toolName}`
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Tool execution failed'
      return `Tool error: ${message}`
    }
  }

  const sendMessage = async (
    content: string,
    options?: {
      model?: string
      provider?: string
      temperature?: number
      maxTokens?: number
      topP?: number
      systemPrompt?: string
      agentId?: string
    }
  ) => {
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return
    
    if (agentStreaming.value[targetAgentId]) {
      cancelCurrentRequest(targetAgentId)
    }
    
    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    const currentMsgs = agentMessages.value[targetAgentId] || []
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: [...currentMsgs, userMessage]
    }

    const agentName = agentStore.activeAgent?.name
    const systemPrompt = options?.systemPrompt ||
      buildLuomiNestSystemPrompt(agentName, agentStore.activeAgent?.systemPrompt)

    const apiMessages: { role: string; content: string }[] = [
      { role: 'system', content: systemPrompt }
    ]
    for (const msg of agentMessages.value[targetAgentId]) {
      if (msg.role === 'system') continue
      if (msg.role === 'assistant' && !msg.done) continue
      apiMessages.push({ role: msg.role, content: msg.content })
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      done: false,
    }
    const msgsWithUser = agentMessages.value[targetAgentId] || []
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: [...msgsWithUser, assistantMessage]
    }
    
    agentStreaming.value[targetAgentId] = true
    agentStreamingContent.value[targetAgentId] = ''

    let convId = agentCurrentConversation.value[targetAgentId]?.id
    if (!convId) {
      const conv = await createConversation(
        content.slice(0, 30),
        targetAgentId,
        options?.model,
        options?.provider
      )
      convId = conv?.id
    }

    const endpoint = convId
      ? `/chat/conversations/${convId}/messages`
      : '/chat/completions'

    const tools = formatToolsForLLM(ALL_LUOMINEST_TOOLS)

    const requestBody: any = {
      messages: apiMessages,
      model: options?.model,
      provider: options?.provider,
      temperature: options?.temperature,
      max_tokens: options?.maxTokens,
      top_p: options?.topP,
      stream: true,
      tools,
    }

    if (targetAgentId) {
      requestBody.agent_id = targetAgentId
    }

    const controller = new AbortController()
    agentAbortControllers.value[targetAgentId] = controller

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const chunkAny = chunk as any

        if (chunkAny.tool_calls && Array.isArray(chunkAny.tool_calls)) {
          const toolCalls = pendingToolCalls.value[targetAgentId] || []
          for (const tc of chunkAny.tool_calls) {
            if (tc.function?.name) {
              toolCalls.push(tc)
            }
          }
          pendingToolCalls.value = {
            ...pendingToolCalls.value,
            [targetAgentId]: toolCalls
            }
          return
        }

        agentStreamingContent.value[targetAgentId] += chunk.content
        const currentMsgList = agentMessages.value[targetAgentId] || []
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...currentMsgList.slice(0, lastIndex), {
              ...currentMsgList[lastIndex],
              content: agentStreamingContent.value[targetAgentId]
            }]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
          const msgListForUsage = agentMessages.value[targetAgentId] || []
          const usageLastIndex = msgListForUsage.length - 1
          if (usageLastIndex >= 0 && msgListForUsage[usageLastIndex]?.role === 'assistant') {
            agentMessages.value = {
              ...agentMessages.value,
              [targetAgentId]: [...msgListForUsage.slice(0, usageLastIndex), {
                ...msgListForUsage[usageLastIndex],
                usage: chunk.usage
              }]
            }
          }
        }
      },
      async () => {
        const toolCalls = pendingToolCalls.value[targetAgentId] || []
        if (toolCalls.length > 0) {
          for (const tc of toolCalls) {
            try {
              const args = typeof tc.function.arguments === 'string'
                ? JSON.parse(tc.function.arguments)
                : tc.function.arguments || {}
              const result = await executeToolCall(tc.function.name, args)
              const toolMsg: ChatMessage = {
                id: `tool-${Date.now()}-${Math.random().toString(36).slice(2)}`,
                role: 'assistant',
                content: `[Tool: ${tc.function.name}] ${result}`,
                timestamp: Date.now(),
                done: true
              }
              const toolMsgList = agentMessages.value[targetAgentId] || []
              agentMessages.value = {
                ...agentMessages.value,
                [targetAgentId]: [...toolMsgList, toolMsg]
              }
            } catch {
            }
          }
          pendingToolCalls.value = {
            ...pendingToolCalls.value,
            [targetAgentId]: []
          }
        }

        delete agentAbortControllers.value[targetAgentId]
        const completeMsgList = agentMessages.value[targetAgentId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...completeMsgList.slice(0, completeLastIndex), {
              ...completeMsgList[completeLastIndex],
              done: true
            }]
          }
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        await fetchConversations(targetAgentId)
        const convId = agentCurrentConversation.value[targetAgentId]?.id
        if (convId) {
          const finalMsgs = agentMessages.value[targetAgentId] || []
          conversationMessagesCache.value = {
            ...conversationMessagesCache.value,
            [convId]: [...finalMsgs]
          }
        }
      },
      (err: string) => {
        delete agentAbortControllers.value[targetAgentId]
        const errorMsgList = agentMessages.value[targetAgentId] || []
        const errorLastIndex = errorMsgList.length - 1
        if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...errorMsgList.slice(0, errorLastIndex), {
              ...errorMsgList[errorLastIndex],
              content: errorMsgList[errorLastIndex].content
                ? `${errorMsgList[errorLastIndex].content}\n\n[Error] ${err}`
                : `[Error] ${err}`,
              done: true
            }]
          }
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        lastError.value = err
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const clearMessages = () => {
    if (activeAgentId.value) {
      agentMessages.value = {
        ...agentMessages.value,
        [activeAgentId.value]: []
      }
      agentCurrentConversation.value = {
        ...agentCurrentConversation.value,
        [activeAgentId.value]: null
      }
    }
    lastError.value = null
  }

  watch(() => activeAgentId.value, async (newAgentId, _oldAgentId) => {
    if (newAgentId) {
      if (!agentConversations.value[newAgentId]) {
        agentConversations.value = {
          ...agentConversations.value,
          [newAgentId]: []
        }
      }
      if (!agentCurrentConversation.value[newAgentId]) {
        agentCurrentConversation.value = {
          ...agentCurrentConversation.value,
          [newAgentId]: null
        }
      }
      if (!agentMessages.value[newAgentId]) {
        agentMessages.value = {
          ...agentMessages.value,
          [newAgentId]: []
        }
      }
      if (!agentStreaming.value[newAgentId]) {
        agentStreaming.value = {
          ...agentStreaming.value,
          [newAgentId]: false
        }
      }
      if (!agentStreamingContent.value[newAgentId]) {
        agentStreamingContent.value = {
          ...agentStreamingContent.value,
          [newAgentId]: ''
        }
      }

      const existingMessages = agentMessages.value[newAgentId]
      const hasExistingMessages = existingMessages && existingMessages.length > 0
      const isCurrentlyStreaming = agentStreaming.value[newAgentId]

      await fetchConversations(newAgentId)

      if (!hasExistingMessages && !isCurrentlyStreaming) {
        const currentConv = agentCurrentConversation.value[newAgentId]
        if (currentConv && currentConv.id) {
          try {
            await loadConversation(currentConv.id)
          } catch (error) {
            agentCurrentConversation.value = {
              ...agentCurrentConversation.value,
              [newAgentId]: null
            }
            agentMessages.value = {
              ...agentMessages.value,
              [newAgentId]: []
            }
          }
        } else if (agentConversations.value[newAgentId].length > 0) {
          const latestConv = agentConversations.value[newAgentId][0]
          if (latestConv && latestConv.id) {
            try {
              await loadConversation(latestConv.id)
            } catch (error) {
            }
          }
        }
      }
    }
  }, { immediate: true })

  return {
    conversations,
    currentConversation,
    messages,
    currentMessages,
    isStreaming,
    isBackendReady,
    isLoadingConversation,
    streamingContent,
    lastError,
    lastUsage,
    activeAgentId,
    pendingToolCalls,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    cacheConversationMessages,
    deleteConversation,
    sendMessage,
    clearMessages,
    cancelCurrentRequest,
    executeToolCall,
  }
})
