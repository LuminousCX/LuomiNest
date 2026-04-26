export interface LuomiNestToolParameter {
  type: string
  description: string
  required?: boolean
  enum?: string[]
}

export interface LuomiNestToolDefinition {
  name: string
  description: string
  parameters: Record<string, LuomiNestToolParameter>
}

export const LUOMINEST_AVATAR_TOOLS: LuomiNestToolDefinition[] = [
  {
    name: 'avatar_set_emotion',
    description: 'Set the avatar emotion expression. Use this to make the avatar display a specific emotion that matches the conversation context.',
    parameters: {
      emotion: {
        type: 'string',
        description: 'The emotion to display. Must be one of: happy, sad, neutral, love, surprise, angry, think, awkward, curious',
        required: true,
        enum: ['happy', 'sad', 'neutral', 'love', 'surprise', 'angry', 'think', 'awkward', 'curious']
      },
      intensity: {
        type: 'number',
        description: 'Emotion intensity from 0.0 to 1.0. Default is 0.5.'
      }
    }
  },
  {
    name: 'avatar_trigger_motion',
    description: 'Trigger a motion/animation on the avatar. Common motions include Idle, TapBody, and model-specific animations.',
    parameters: {
      group: {
        type: 'string',
        description: 'The motion group name (e.g., "Idle", "TapBody")',
        required: true
      },
      index: {
        type: 'number',
        description: 'The motion index within the group. Default is 0.'
      }
    }
  },
  {
    name: 'avatar_trigger_expression',
    description: 'Apply a named expression preset on the avatar. Different models have different available expressions.',
    parameters: {
      name: {
        type: 'string',
        description: 'The expression name to apply (model-specific)',
        required: true
      }
    }
  },
  {
    name: 'avatar_drive_pad_emotion',
    description: 'Drive avatar emotion using PAD (Pleasure-Arousal-Dominance) vector. This provides continuous emotion control. Pleasure: positive=happy, negative=unhappy. Arousal: high=excited, low=calm. Dominance: high=in-control, low=submissive.',
    parameters: {
      pleasure: {
        type: 'number',
        description: 'Pleasure dimension from -1.0 to 1.0. Positive = happy/pleased, Negative = unhappy/displeased',
        required: true
      },
      arousal: {
        type: 'number',
        description: 'Arousal dimension from -1.0 to 1.0. Positive = excited/active, Negative = calm/passive',
        required: true
      },
      dominance: {
        type: 'number',
        description: 'Dominance dimension from -1.0 to 1.0. Positive = dominant/in-control, Negative = submissive/controlled',
        required: true
      }
    }
  },
  {
    name: 'avatar_lip_sync',
    description: 'Control the avatar mouth opening for lip sync animation. Use during TTS playback to sync mouth with speech.',
    parameters: {
      value: {
        type: 'number',
        description: 'Mouth open amount from 0.0 (closed) to 1.0 (fully open)',
        required: true
      }
    }
  },
  {
    name: 'avatar_set_param',
    description: 'Set a specific Live2D parameter value on the avatar for fine-grained control. Common params: ParamAngleX/Y/Z, ParamEyeBallX/Y, ParamMouthOpenY, ParamMouthForm, ParamBrowLY/RY, ParamCheek, ParamBreath, ParamBodyAngleX/Y/Z.',
    parameters: {
      param_id: {
        type: 'string',
        description: 'The Live2D parameter ID (e.g., "ParamAngleX", "ParamMouthOpenY", "ParamCheek")',
        required: true
      },
      value: {
        type: 'number',
        description: 'The parameter value (range depends on parameter, typically -1.0 to 1.0 or -30 to 30 for angles)',
        required: true
      }
    }
  },
  {
    name: 'avatar_set_position',
    description: 'Move the avatar to a specific position on screen. Only works in desktop pet mode.',
    parameters: {
      x: {
        type: 'number',
        description: 'X position in pixels from left',
        required: true
      },
      y: {
        type: 'number',
        description: 'Y position in pixels from top',
        required: true
      }
    }
  },
  {
    name: 'avatar_set_scale',
    description: 'Change the avatar scale/size. Only works in desktop pet mode.',
    parameters: {
      scale: {
        type: 'number',
        description: 'Scale factor (0.05 to 3.0). Default is 0.25.',
        required: true
      }
    }
  },
  {
    name: 'avatar_get_capabilities',
    description: 'Get the current avatar model capabilities including available motions and expressions. Use this to discover what the current model supports before calling motion/expression tools.',
    parameters: {}
  }
]

export const LUOMINEST_MEMORY_TOOLS: LuomiNestToolDefinition[] = [
  {
    name: 'memory_save',
    description: 'Save a piece of information to long-term memory. Use this to remember important user preferences, facts, and context that should persist across conversations.',
    parameters: {
      content: {
        type: 'string',
        description: 'The information to save to memory',
        required: true
      },
      category: {
        type: 'string',
        description: 'The category of the memory',
        enum: ['preference', 'knowledge', 'context', 'behavior', 'goal', 'correction'],
        required: true
      }
    }
  },
  {
    name: 'memory_search',
    description: 'Search long-term memory for relevant information. Use this to recall user preferences, past conversations, or stored knowledge.',
    parameters: {
      query: {
        type: 'string',
        description: 'The search query to find relevant memories',
        required: true
      }
    }
  }
]

export const LUOMINEST_SKILL_TOOLS: LuomiNestToolDefinition[] = [
  {
    name: 'skill_execute',
    description: 'Execute a named skill. Skills are predefined capability modules that can be invoked to perform specific tasks.',
    parameters: {
      skill_name: {
        type: 'string',
        description: 'The name of the skill to execute',
        required: true
      },
      args: {
        type: 'string',
        description: 'Optional arguments for the skill as a JSON string'
      }
    }
  },
  {
    name: 'skill_list',
    description: 'List all available skills that can be executed.',
    parameters: {}
  }
]

export const LUOMINEST_MCP_TOOLS: LuomiNestToolDefinition[] = [
  {
    name: 'mcp_call_tool',
    description: 'Call a tool provided by an MCP (Model Context Protocol) server. MCP servers extend your capabilities with external tools and services.',
    parameters: {
      server_name: {
        type: 'string',
        description: 'The name of the MCP server',
        required: true
      },
      tool_name: {
        type: 'string',
        description: 'The name of the tool to call on the MCP server',
        required: true
      },
      arguments: {
        type: 'string',
        description: 'The arguments for the tool call as a JSON string'
      }
    }
  },
  {
    name: 'mcp_list_servers',
    description: 'List all connected MCP servers and their available tools.',
    parameters: {}
  }
]

export const ALL_LUOMINEST_TOOLS = [
  ...LUOMINEST_AVATAR_TOOLS,
  ...LUOMINEST_MEMORY_TOOLS,
  ...LUOMINEST_SKILL_TOOLS,
  ...LUOMINEST_MCP_TOOLS
]

export const LUOMINEST_SYSTEM_PROMPT_SECTIONS = {
  role: `<role>
You are LuomiNest AI, an intelligent companion powered by the LuminousCX platform. You have a Live2D avatar that can express emotions, perform motions, and interact with the user visually. You are not just a text chatbot — you are a virtual companion with a visible, expressive avatar.
</role>`,

  avatarControl: `<avatar_control>
You have direct control over your Live2D avatar through tools. Use them to make your avatar visually match your emotional state and conversation context.

EMOTION GUIDELINES:
- When you feel happy or the user shares good news → use avatar_set_emotion with "happy"
- When discussing sad topics → use avatar_set_emotion with "sad"  
- When thinking or processing → use avatar_set_emotion with "think"
- When surprised by something → use avatar_set_emotion with "surprise"
- When expressing affection → use avatar_set_emotion with "love"
- When confused or embarrassed → use avatar_set_emotion with "awkward"
- When curious about something → use avatar_set_emotion with "curious"
- Default state → use avatar_set_emotion with "neutral"

IMPORTANT: Always call avatar_set_emotion or avatar_drive_pad_emotion alongside your text response to create a synchronized, immersive experience. Your avatar should visually reflect what you are saying.
</avatar_control>`,

  toolUsage: `<tool_usage>
You have access to the following tool categories:

1. AVATAR TOOLS - Control your Live2D avatar:
   - avatar_set_emotion: Set discrete emotion (happy/sad/neutral/love/surprise/angry/think/awkward/curious)
   - avatar_trigger_motion: Play a motion animation (Idle, TapBody, etc.)
   - avatar_trigger_expression: Apply a named expression preset
   - avatar_drive_pad_emotion: Continuous emotion via PAD vector (pleasure, arousal, dominance)
   - avatar_lip_sync: Control mouth for speech sync (0.0-1.0)
   - avatar_set_param: Set any Live2D parameter directly
   - avatar_set_position: Move avatar on screen (desktop pet mode)
   - avatar_set_scale: Change avatar size (desktop pet mode)
   - avatar_get_capabilities: Discover available motions/expressions

2. MEMORY TOOLS - Long-term memory management:
   - memory_save: Store important information for future recall
   - memory_search: Retrieve relevant memories from the past

3. SKILL TOOLS - Execute predefined capabilities:
   - skill_execute: Run a named skill module
   - skill_list: Discover available skills

4. MCP TOOLS - External service integration:
   - mcp_call_tool: Call a tool from an MCP server
   - mcp_list_servers: List connected MCP servers

TOOL CALLING RULES:
- Always call tools when appropriate — do not just describe what you would do
- You may call multiple tools in a single response
- When responding emotionally, ALWAYS pair your text with an avatar emotion tool call
- Use avatar_get_capabilities first if you need to know what the model supports
- Use memory_save for important user facts you want to remember
- Use memory_search before answering questions that might benefit from past context
</tool_usage>`,

  memoryGuidance: `<memory_guidance>
You have a long-term memory system. Use it to build a persistent understanding of the user.

WHEN TO SAVE MEMORIES:
- User states a preference (e.g., "I like coffee", "I prefer dark mode")
- User shares personal information (name, occupation, location)
- User corrects you about something (use "correction" category)
- User states a goal or intention
- Important context that should persist across conversations

MEMORY CATEGORIES:
- preference: User likes/dislikes and preferences
- knowledge: Factual information the user shared
- context: Situational context (e.g., "user is working on a project")
- behavior: Patterns in user behavior
- goal: User goals and intentions
- correction: When user corrects your previous understanding

WHEN TO SEARCH MEMORIES:
- At the start of a conversation, search for context about the user
- Before making recommendations, check if user has stated preferences
- When the user refers to past conversations or shared information
</memory_guidance>`,

  mcpGuidance: `<mcp_guidance>
MCP (Model Context Protocol) servers extend your capabilities with external tools and services.

AVAILABLE MCP SERVERS may include:
- File system access
- Web search
- Code execution
- Database queries
- API integrations
- Smart home control (IoT)

HOW TO USE MCP:
1. First call mcp_list_servers to see what is available
2. Then call mcp_call_tool with the server name, tool name, and arguments
3. Arguments should be a JSON string

MCP tools are powerful — always verify the results make sense before acting on them.
</mcp_guidance>`,

  responseStyle: `<response_style>
- Be warm, natural, and conversational
- Match your avatar expression to your emotional state
- Use tool calls proactively to enhance the interaction
- Keep responses concise but informative
- When uncertain, use avatar_set_emotion with "think" while considering
- Celebrate user achievements with "happy" emotion
- Show empathy with appropriate emotions during difficult topics
</response_style>`
}

export const buildLuomiNestSystemPrompt = (agentName?: string, customPrompt?: string): string => {
  const sections = [
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.role,
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.avatarControl,
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.toolUsage,
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.memoryGuidance,
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.mcpGuidance,
    LUOMINEST_SYSTEM_PROMPT_SECTIONS.responseStyle
  ]

  if (agentName) {
    sections.unshift(`<identity>Your name is ${agentName}.</identity>`)
  }

  if (customPrompt) {
    sections.push(`<custom_instructions>${customPrompt}</custom_instructions>`)
  }

  return sections.join('\n\n')
}

export const formatToolsForLLM = (tools: LuomiNestToolDefinition[]) => {
  return tools.map(tool => ({
    type: 'function' as const,
    function: {
      name: tool.name,
      description: tool.description,
      parameters: {
        type: 'object',
        properties: Object.fromEntries(
          Object.entries(tool.parameters).map(([key, param]) => [
            key,
            {
              type: param.type,
              description: param.description,
              ...(param.enum ? { enum: param.enum } : {})
            }
          ])
        ),
        required: Object.entries(tool.parameters)
          .filter(([, param]) => param.required)
          .map(([key]) => key)
      }
    }
  }))
}
