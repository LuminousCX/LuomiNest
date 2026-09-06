"""工作流内部工具处理函数（按域拆分包）。

原 register_tools.py（约 2000 行）的处理函数按域拆到本包：

- common.py           : 事件推送器管理 + _wf_catch 统一异常装饰器
- memory_tools.py     : memory.*（记忆中枢）
- schedule_tools.py   : schedule.*（定时任务）
- market_tools.py     : market.*（扩展市场）
- platform_tools.py   : platform.*（平台实例）
- smart_home_tools.py : smart_home.*（智能家居）
- console_tools.py    : console.execute / subagent.delegate / context.compress（单工具域）

工具注册（注册顺序、工具名、schema）仍统一保留在
register_tools.register_internal_tools 中，本包只承载处理函数。
"""

from app.core.workflow.tool_domains.common import (
    _get_emitter,
    _wf_catch,
    remove_emitter,
    set_emitter,
)
from app.core.workflow.tool_domains.console_tools import (
    _console_execute,
    _context_compress,
    _subagent_delegate,
)
from app.core.workflow.tool_domains.market_tools import (
    _market_get_leaderboard,
    _market_install,
    _market_list_installed,
    _market_uninstall,
)
from app.core.workflow.tool_domains.memory_tools import (
    _memory_append_daily,
    _memory_build_context,
    _memory_clear_facts,
    _memory_create_fact,
    _memory_delete_fact,
    _memory_distill,
    _memory_get_daily,
    _memory_get_knowledge,
    _memory_get_profile,
    _memory_get_summary,
    _memory_list_dailies,
    _memory_list_facts,
    _memory_promote_conversation_facts,
    _memory_search,
    _memory_update_fact,
    _memory_update_knowledge,
    _memory_update_profile,
    _memory_update_summary,
    _memory_vector_rebuild,
    _require_memory_engine,
)
from app.core.workflow.tool_domains.platform_tools import (
    _platform_list_instances,
    _platform_send_message,
    _platform_start_instance,
    _platform_stop_instance,
)
from app.core.workflow.tool_domains.schedule_tools import (
    _schedule_create,
    _schedule_delete,
    _schedule_get,
    _schedule_list,
)
from app.core.workflow.tool_domains.smart_home_tools import (
    _smart_home_control,
    _smart_home_list_devices,
    _smart_home_list_scenes,
)
