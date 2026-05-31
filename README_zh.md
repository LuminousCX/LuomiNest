Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

Inline comments:
In `@backend/app/api/v1/endpoints/memory.py`:
- Around line 202-220: The delete_fact and update_fact endpoints currently call
storage.delete_fact and storage.update_fact via await asyncio.to_thread(...) but
don't handle the ValueError those storage methods raise when a fact_id doesn't
exist; wrap each await asyncio.to_thread(...) call in a try/except catching
ValueError and raise a FastAPI HTTPException(status_code=404, detail=str(err))
(or a clear message) so the endpoint returns 404 Not Found instead of 500; keep
the existing function names delete_fact and update_fact and only add the
try/except around the storage.delete_fact and storage.update_fact invocations.

In `@backend/app/engines/memory/core/event_bus.py`:
- Around line 58-69: The publish method (publish) currently appends the same
MemoryEvent into _pending for each matching subscriber and calls await
self._queue.put(event) inside the subscriber loop, which enqueues the identical
event multiple times; change it so the event is queued exactly once per publish:
iterate subscribers to populate/append event into each subscriber's entry in
_pending, but move await self._queue.put(event) outside the for
subscriber_id,... loop (or otherwise ensure you enqueue only a single
marker/event per publish), keeping _pending as the per-subscriber delivery list
and leaving _consume_loop to dequeue once and dispatch to all pending
subscribers' callbacks.

In `@backend/app/engines/memory/core/migration.py`:
- Around line 50-65: The current merge helpers (_merge_profiles,
_merge_user_context, _merge_history) choose either base or incoming based solely
on _count_profile_fields/_count_context_fields/_count_history_fields which can
drop non-empty fields from the winner; change each function to perform per-field
merges: for scalar fields prefer non-empty value (keep base value unless empty
then take incoming), for list/sequence fields produce a stable union (append
incoming items not present, preserving order), for dict/map fields merge keys
with incoming values only filling missing keys or merging values recursively if
needed, and for History specifically concatenate events preserving order and
deduplicating by a stable key; remove the global count-based selection and use
these per-field rules so no non-empty field from either side is lost.

In `@backend/app/engines/memory/core/semantic_matcher.py`:
- Around line 134-138: get_semantic_matcher() can race and create multiple
SemanticMatcher instances; wrap the creation in a lock (use the existing
_user_space_lock or add a dedicated _semantic_matcher_lock) and apply
double-checked locking: check _semantic_matcher_instance, acquire the lock,
re-check _semantic_matcher_instance, then instantiate SemanticMatcher and assign
it to _semantic_matcher_instance before releasing the lock to ensure thread-safe
singleton initialization.

In `@backend/app/engines/memory/core/user_space.py`:
- Around line 178-183: The loop that copies summaries can raise AttributeError
because user_section (from getattr(user.user_context, section, None)) may be
None; update the condition to ensure user_section is not None before accessing
its attributes (e.g., change the check to: if agent_section and
agent_section.summary and user_section and not user_section.summary) or, if
intended, instantiate and attach a missing section object to user.user_context
before assigning summary; refer to agent_memory.user, user.user_context, and the
loop variable section to locate the code to modify.

In `@backend/app/engines/memory/search/embedding_index.py`:
- Around line 44-56: The loop over `ranked` in `embedding_index.py` reweights
scores using `TIER_SEARCH_WEIGHT` but breaks once `results` reaches `top_k`,
which truncates by semantic score before tier weighting; instead, iterate
through all items in `ranked`, use `_passes_filter` to skip disallowed facts,
compute `weighted_score = score * TIER_SEARCH_WEIGHT.get(fact.tier, 1.0)`,
collect candidates that meet `min_score` into a list, then sort that list by
`weighted_score` descending and finally truncate to `top_k` before
returning—this ensures tier weights affect global ranking rather than only the
pre-truncated subset.

In `@backend/app/engines/memory/search/memory_search.py`:
- Around line 30-35: The code in memory_search.py is accessing MemoryStorage's
private attribute _storage_path to enumerate agent JSON files; add a public
method on MemoryStorage (e.g., list_agents() or
iter_agent_memories()/get_agents_files()) that returns agent identifiers or file
paths or yields loaded AgentMemory objects, implement that in
backend/app/engines/memory/core/storage.py alongside existing
load_agent_memory/save_agent_memory, and update memory_search.py to call the new
public API (replace use of self._storage._storage_path / "agents" and direct
globbing with self._storage.list_agents() or self._storage.iter_agent_memories()
and then use load_agent_memory or use yielded AgentMemory objects) so the module
no longer depends on the private _storage_path internals.

In `@frontend/src/renderer/src/views/MemoryView.vue`:
- Around line 239-240: 在 saveEdit 和 handleDeleteFact 的空 catch {}
中补上错误处理：不要吞掉异常，而是捕获为 e（或 err），将其记录到控制台或现有 logger（例如 console.error 或 this.$notify
/ useToast），并为用户显示失败提示（例如 “保存失败”/“删除失败”）或在开发模式下展示详细错误信息；确保在 saveEdit 和
handleDeleteFact 的 catch 块中引用相同的错误变量名并返回/抛出或优雅退回到安全状态以避免不一致。

In `@新建` 文本文档.md:
- Around line 1-3: Remove the accidentally committed draft file "新建 文本文档.md"
from the PR (it contains chatty design notes and obsolete draft code such as
EmbeddingIndex and mismatched dataclass definitions vs models.py); either delete
the file from the branch or move a cleaned, finalized design into docs/ with a
meaningful filename, and update the commit/PR to reflect the deletion or
relocation so the repo no longer contains the temporary draft and any references
to EmbeddingIndex or conflicting dataclass snippets are removed.

---

Outside diff comments:
In `@backend/app/engines/memory/core/updater.py`:
- Around line 375-381: The return value in update_from_conversation currently
hardcodes "should_be_global: True", which is misleading; change the return to
accurately reflect the distribution of added facts by removing the hardcoded
field and instead return counts like "global_facts_added" and
"agent_facts_added" (compute these from the facts in facts_added, e.g., by
checking each fact's should_be_global flag) so callers get the same style as
memory_engine.py; update the return dict in updater.py (function
update_from_conversation) to include those counts and adjust any callers that
expect should_be_global accordingly.

---

Nitpick comments:
In `@backend/app/engines/memory/core/distiller.py`:
- Around line 5-12: Remove the unused imports MemoryTier and TIER_SEARCH_WEIGHT
from the import list in distiller.py; update the from .models import block
(which currently includes UserSpace, AgentMemory, MemoryTier,
TIER_SEARCH_WEIGHT, utc_now_iso_z, DistilledSection) by deleting MemoryTier and
TIER_SEARCH_WEIGHT so only the actually used symbols remain (UserSpace,
AgentMemory, utc_now_iso_z, DistilledSection), and run linting to confirm no
other unused imports exist.
- Line 79: Both distill_user_space and distill_agent_memory are missing a type
annotation for the llm_adapter parameter; add a proper type hint (preferably the
project LLM adapter interface/class, e.g. LLMAdapter or AdapterInterface) on the
llm_adapter parameter in async def distill_user_space(self, user_space:
UserSpace, llm_adapter: LLMAdapter) -> DistilledSection and the corresponding
signature in distill_agent_memory, and import that type (or fall back to
typing.Any if no specific adapter type exists) so IDEs and linters recognize the
type.

In `@backend/app/engines/memory/core/injector.py`:
- Around line 229-254: Both _format_v3_episodic_events and
_format_episodic_events duplicate filtering, sorting and top-3 formatting logic;
extract that shared logic into a private helper (e.g. _format_event_lines) that
accepts a list of events and user_query, performs the matches_query filter,
sorts by time_distance_days(), formats the top 3 lines (time_label, tags,
sanitized core_goal, optional sanitized key_information truncated to 80 chars)
and returns the header + joined lines or None; then have
_format_v3_episodic_events call this helper with user_space.episodic_events +
agent_memory.agent_events and _format_episodic_events call it with
memory_data.episodic_events so both functions simply assemble their event list
and delegate formatting.

In `@backend/app/engines/memory/core/memory_engine.py`:
- Around line 421-435: The hardcoded distillation thresholds
(len(user_space.facts) >= 15 and len(agent_memory.agent_facts) >= 10) should be
extracted into configurable class-level constants (e.g.,
USER_SPACE_DISTILL_THRESHOLD and AGENT_MEMORY_DISTILL_THRESHOLD) or injected via
the MemoryEngine constructor/config so they can be adjusted without editing
logic; update the conditions in the MemoryEngine method to use these constants
instead of literals, ensure any default values match current behavior, and
propagate the config into any places that construct MemoryEngine so tests and
runtime can override them if needed (references: user_space.facts check,
agent_memory.agent_facts check, _distiller.distill_user_space,
_distiller.distill_agent_memory, _storage.save_user_space,
_storage.save_agent_memory).

In `@backend/app/engines/memory/core/models.py`:
- Around line 434-450: MemoryData.resolve_conflicts currently calls
UserSpace._facts_conflict, creating tight coupling; extract the conflict check
into a module-level function (e.g., facts_conflict(content_a, content_b)) or a
small util class, then change resolve_conflicts to call that new function
instead of UserSpace._facts_conflict; update imports/namespace so
resolve_conflicts (which iterates self.facts, appends to self.archived_facts,
and returns removed_ids for a MemoryFact new_fact) uses the new
facts_conflict(new_lower, existing.content) helper and remove any dependency on
UserSpace.

In `@backend/app/engines/memory/core/semantic_matcher.py`:
- Around line 37-38: The open(...) call in semantic_matcher.py unnecessarily
passes the read mode string; update the code that loads cached embeddings (the
with open(self._cache_path, "r", encoding="utf-8") as f: block that assigns
self._embeddings = json.load(f)) to omit the explicit "r" parameter and just use
with open(self._cache_path, encoding="utf-8") as f: so the default read mode is
used.
- Around line 53-64: compute_embedding currently updates the in-memory
_embeddings dict but never persists it, so computed embeddings can be lost;
after storing embedding in compute_embedding (inside the with self._lock block
where self._embeddings[fact.id] is set) call the persistence method
_save_cache() (await it if it's async, or call it asynchronously/schedule it to
avoid blocking) so each computed embedding is saved; ensure you handle
exceptions from _save_cache() and keep the lock/synchronization consistent with
_save_cache's expectations.

In `@backend/app/engines/memory/core/storage.py`:
- Around line 256-273: The delete_fact method (and similarly update_fact)
currently raises ValueError when fact_id is missing while its signature returns
bool; pick one approach and make it consistent: either (A) document the
exception by updating the function signature/type hints and docstring for
delete_fact and update_fact to declare that ValueError is raised when a fact is
not found (mentioning load_agent_memory, load_user_space, save_agent_memory,
save_user_space as involved helpers), or (B) change the behavior to return False
instead of raising—i.e., replace the raise ValueError(...) branches with return
False and ensure callers handle the False result and that
save_agent_memory/save_user_space still return booleans; apply the same change
consistently to update_fact.

In `@backend/app/engines/memory/export/markdown_parser.py`:
- Line 6: The file imports logger from loguru but never uses it; remove the
unused import statement "logger" (i.e., delete or change the line importing
logger) so there are no unused imports in markdown_parser.py and ensure nothing
else references logger in that module (search for "logger" to confirm) before
committing.
- Around line 159-167: The MemoryFact creation hardcodes
tier="long_term_preference" (in the MemoryFact instantiation) so imported agent
facts always get that tier; update the markdown importer (where MemoryFact is
constructed) to derive tier from the parsed markdown metadata/frontmatter (or
fallback to "long_term_preference" if missing) — e.g., extract a "tier" field
from the parsed document and pass it into the MemoryFact constructor instead of
the literal, and ensure the parsing function validates/normalizes allowed tier
values before assignment.
- Around line 132-133: Move the in-loop import of EpisodicEvent out of the loop
and add "from app.engines.memory.core.models import EpisodicEvent" to the
module-level import block at the top of the file (with the other imports), then
remove the import statement inside the loop so the code instantiates
EpisodicEvent(core_goal=content[:200]) directly without re-importing.

In `@backend/app/services/chat_service.py`:
- Around line 23-26: _Remove the unnecessary _get_llm_adapter() wrapper and use
the module-level llm_adapter directly: delete the _get_llm_adapter staticmethod
and replace any calls like self._get_llm_adapter() or
ChatService._get_llm_adapter() with the already-imported llm_adapter symbol;
ensure places that construct or pass an llm_adapter parameter (e.g., the call
that currently supplies llm_adapter via _get_llm_adapter) now pass
llm_adapter=llm_adapter directly and keep the existing top-level import of
llm_adapter.

In `@backend/app/services/context_service.py`:
- Around line 20-23: The _get_llm_adapter function accepts a provider_name
parameter that is unused and returns the global llm_adapter; either remove the
unused parameter from the _get_llm_adapter signature and update any callers to
stop passing provider_name, or implement provider-based lookup: change
_get_llm_adapter(provider_name: str | None = None) to import the adapter
registry or provider map (e.g., a dict of adapters or a factory in
app.runtime.provider.llm.adapter), return the adapter matching provider_name
when provided, fall back to the default llm_adapter when provider_name is None,
and raise a clear error (ValueError) if a non-empty provider_name has no
matching adapter; update tests/call sites accordingly.

In `@frontend/src/renderer/src/stores/memory.ts`:
- Around line 121-152: Replace the use of apiGet<any> and the `as any` casts by
defining a proper response interface (e.g., MemoryApiResponse) describing both
v3 and v2 payload shapes (including raw.user_space, raw.agent_memory, version,
last_updated, working_memory, etc.), update the call to
apiGet<MemoryApiResponse>, and update the v2 downgrade branch that builds
memoryData.value (the object assigned to memoryData.value in the fetch logic) to
populate the missing `version` and `last_updated` fields and remove `as any` on
agent_memory; ensure all accesses use the typed properties (raw.user_space,
raw.agent_memory, mem.*) so TypeScript enforces correctness.

In `@frontend/src/renderer/src/views/MemoryView.vue`:
- Line 56: 在 MemoryView.vue 中不要用 any[]：为搜索结果定义一个接口（例如 SearchMemoryResult 包含
id、title、snippet、createdAt 等实际字段），然后把 const searchMemoryResults = ref<any[]>([])
改为使用该接口类型（例如 ref<SearchMemoryResult[]>([]) 或者
Ref<SearchMemoryResult[]>），并在文件顶部或单独的 types 文件中导出/导入该接口以提高类型安全性并更新所有对
searchMemoryResults 的访问以匹配新字段名。