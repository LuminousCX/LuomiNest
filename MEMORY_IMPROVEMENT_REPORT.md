# 记忆系统改进报告（2026-09-16）

> 本次改进基于此前三轮审查（代码审查 → 性能分析 → 基准测试）的结论实施。
> 所有改动未提交，保留在工作区供审查：`git diff` 查看；两个验证脚本保留在
> `backend/scripts/` 可反复运行。

## 一、改了什么（11 个文件）

### 提交 1 主题：修复向量索引正确性 + 消除 N+1 + 连接复用 + 消除重复写

| 文件 | 改动 |
|---|---|
| `vector_store.py` | ① `LLMEmbeddingProvider` 重写：长生命周期 httpx 连接池（配置变更自动重建）、空 api_key 允许（本地 Ollama 可用）、`aclose`；② 新增 `_coerce_vectors` 嵌入契约校验（错误协议 fail-loud 抛 ValueError，替代静默产出 `()` 标量）；③ `embed_batch` 批量助手；④ `dedup_check` 支持预算向量 `query_vec`、`batch_add` 支持 `pre_vectors`（跳过重复嵌入）；⑤ `_load` 冷启动维度校验，自动剔除并删除历史标量垃圾/错维行；⑥ `batch_add` 落盘失败回滚内存索引（修复"内存有库里无→永远补不回"的缺口）；⑦ `clear_for_rebuild`（作用域：agent 级+指定对话，不动其他对话）；⑧ 构造时 mkdir（修本地模式 unable to open database file） |
| `memory_engine.py` | **核心接线修复**：`_get_vector_manager` 不再把单文本协议的 `LLMProvider` 直接注入，统一包装为 `LLMEmbeddingProvider`（批量协议）——这是全索引标量化的根因；新增 `write_lock` 属性；引擎层 `merge_facts` 调用移入 `to_thread` |
| `vector_manager.py` | `dedup_and_add` 批量化：一次批量嵌入 → 复用向量判重 → 复用向量入库（N+1 次 HTTP → 1 次，向量只算一遍）；`rebuild` 先清旧再建（修复已删事实被持续召回、索引只增不减） |
| `extractor.py` | supersedes 收口：`_parse_facts_from_raw` 改为纯解析不落库，supersedes 以 ops 返回、由调用方在写锁内统一应用（K 条 supersedes 从 K 次全量 save → 并入既有 1 次）；事实内容截断 500 字符、置信度夹取 [0,1]；所有 `merge_facts` 调用移入 `to_thread`（不再阻塞事件循环）；蒸馏的对话级 store 改为轨道感知路径（修复 users 轨引擎潜在写错目录） |
| `chat_completions.py` | `embed` 改用共享连接池（旧版 `self._client` 为 None 时每次新建临时 client，逐次付 TCP/TLS 握手） |
| `memory/__init__.py` | `shutdown_memory` 补向量库与 embedding 连接池的 `aclose` 链 |

### 提交 2 主题：分词预计算 + 中文双字词 + 写入原子化

| 文件 | 改动 |
|---|---|
| `store.py` | 新增 `mutate(fn)`：读-改-写序列在 store 锁内原子执行并返回结果 |
| `fact_manager.py` | ① 常用中文双字词优先整体成词（~90 词表，"咖啡"不再拆成"咖"+"啡"）；② `_find_similar_fact` 存量事实分词预计算一次复用（旧版每层循环重复分词）；③ add/remove/update/clear/cleanup 五个写方法收进 `mutate`（修复并发读-改-写相互覆盖） |
| `memory.py` 端点 | 事实 CRUD 四个写端点挂 `engine.write_lock` + `to_thread`（与蒸馏/画像更新互斥） |
| `context_service.py` | 自然语言 forget 挂 `engine.write_lock` + 原子 `mutate` |
| `memory_tools.py` | 工作流四个写工具挂同一写锁（补 `import asyncio`——该文件原无测试覆盖） |

## 二、准确性验证：32/32 通过

脚本：`backend/scripts/memory_verify.py`（LLM 在适配器边界替换为固定应答，其余全走真实生产代码路径）

| # | 验证项 | 结果 |
|---|---|---|
| ① | **端到端记忆**：说"我叫洛米，喜欢喝拿铁咖啡"→ 姓名入档案、偏好入 Agent 轨、上下文入对话轨；提问"咖啡"→ 注入包含拿铁；对话内提问 → 对话级事实注入；向量检索"咖啡"命中 | 6/6 ✓ |
| ② | **生产装配链路**：真实 `OpenAICompatibleProvider` + 真实形状的批量 embeddings 响应 → 向量 (1536,) 非标量、5 条事实仅 1 次 HTTP（旧链路 6 次且全标量） | 2/2 ✓ |
| ③ | 契约防护：错误协议 provider 触发 ValueError（旧版静默产出 `()` 标量垃圾） | ✓ |
| ④ | 存量垃圾清洗：预埋标量行 + 错维行 → 冷启动剔除并删除，检索只返回有效事实 | 2/2 ✓ |
| ⑤ | 合并语义：重复内容不翻倍；同类别矛盾 → 旧事实归档（is_latest=False + history）；LLM correction → 旧事实置信度降 ≤0.3 | 7/7 ✓ |
| ⑥ | supersedes 收口：3 条 supersedes 全部生效，全流程 save 次数 = 1（旧版 ≥4） | 2/2 ✓ |
| ⑦ | 对话级隔离：A 对话事实对 B 对话不可见 | 2/2 ✓ |
| ⑧ | 群友画像块：多成员轨读取 + 排除说话成员 | 2/2 ✓ |
| ⑨ | 自然语言 forget：匹配事实被遗忘、无关事实不受影响 | 2/2 ✓ |
| ⑩ | 并发写：20 路并发 update 经写锁后零丢失（旧版存在覆盖窗口） | ✓ |
| ⑪ | rebuild 清旧：删除事实后重建，不再被召回；存留事实仍可召回 | 2/2 ✓ |
| ⑫ | 入库防护：超长内容截断 500、越界置信度夹取、低于阈值(0.7)丢弃 | 3/3 ✓ |

回归：**全量 pytest 203 passed**（与改动前基线完全一致，零回归）。

## 三、速度数据

脚本：`backend/scripts/memory_benchmark.py`
（RTT 为模拟值并已标注；HTTP 调用数为真实计数；SQLite/CPU 指标真实实测；
"改动前基线"= 今晨在改动前代码上同机实测；"旧算法复刻"= 在新存储层上
复刻旧调用模式，两者只差调用模式，对照公平）

### A. 向量索引 dedup_and_add（N=30 条新事实）

| 场景 | HTTP 调用 | embed 文本 | 墙钟 |
|---|---|---|---|
| 改动前基线 RTT=200ms | 31 | 60 | 6330.8 ms |
| 旧算法复刻 RTT=200ms | 31 | 60 | 6411.6 ms |
| **新实现 RTT=200ms** | **1** | **30** | **253.1 ms** |

**提速 25.3 倍**（RTT=50ms 档为 22.9 倍：1969.9→86.0ms）。
旧算法复刻与改动前基线吻合（±1.3%），证明对照有效。
注意：改动前那 6.3 秒产出的全是 `()` 标量垃圾——**速度与正确性是同一次修复**。

### B. 本地指标（与改动前基线同口径）

| 指标 | 基线 | 现在 | 变化 |
|---|---|---|---|
| merge_facts 100存量+50新增 | 130.41 ms | **91.31 ms** | **-30%（1.4x）** |
| save_data 全量替换 100条 | 17.75 ms | 17.12 ms | 无回归 |
| load_data 冷启动 100条 | 7.11 ms | 7.14 ms | 无回归 |
| _rank_candidates 100向量 | 0.63 ms | 0.44 ms | 无回归（略快） |
| _rank_candidates 1000向量 | 4.90 ms | 3.46 ms | 无回归（略快） |
| _load 冷启动 1000向量 | 28.14 ms | 27.31 ms | 无回归 |

merge_facts 的 1.4x 来自分词预计算（每存量事实分词 1 次而非 2 次）+ 双字词
缩小词集合；且该函数已全部移出事件循环（`to_thread`），不再卡其他请求。

### D. 端到端链路（LLM 提取即时返回）

| embedding RTT | 写入（提取+合并+落库+向量化） | 注入（含向量召回） |
|---|---|---|
| 0ms（本地推理） | 83.4 ms | 8.2 ms |
| 200ms（远端 API） | 413.7 ms（1 次批量嵌入） | 224.2 ms |

对照：改动前同条件写入路径需 31 次串行 embed ≈ 6.3s+（端到端约 **15 倍**）。

### E. 响应路径专项（回复关键上的记忆耗时）

回复链路上记忆的三个位置（chat_service.py）：
- **注入（读）**：LLM 调用前内联（:748/:950）——每条回复都付；
- **记忆写**：流式模式在 done 事件之后后台执行（用户无感）；**非流式模式内联在返回前**（用户要等）；
- **蒸馏**：后台任务。

| 账目 | 旧版 | 新版 | 变化 |
|---|---|---|---|
| 非流式回复的记忆写等待 | +6330ms（RTT=200ms） | +253ms | **25 倍** |
| 事件循环停顿（写入期间，影响并发请求） | ~130ms 连续冻结（merge 裸跑循环线程） | ≤35.8ms（GIL/调度噪声，非连续冻结） | 3.6 倍 |
| 注入（稳态，含 1 次 embed RTT） | RTT + 本地 ~7-17ms（但排序是垃圾） | RTT + 本地 ~7-17ms（真实语义排序） | 持平，正确性修复 |
| 冷启动向量调用连接建立 | ~174.6ms/次（逐次新建 client） | ~6.7ms/次（常驻连接池） | 26 倍（回环下界） |

注：E3 的 174ms/次为回环 TCP 实测，主因是 httpx.AsyncClient 逐次构造（含 SSL 上下文）；
真实远端 TLS 握手更贵。旧版 embed 在"该适配器已发过聊天请求"时会复用共享池
（`self._client` 非 None），逐次新建只发生在首次向量调用/纯记忆流程——新版统一常驻池，
配置变更自动重建。

## 四、顺手修掉的额外问题（审查中发现、本次一并处理）

1. `batch_add` 先更内存后落盘、落盘失败不回滚 → 永久缺口（已修：回滚）
2. `rebuild` 不清旧向量 → 已删事实持续被召回、索引只增不减（已修：作用域清旧）
3. 事实内容无长度上限、置信度不夹取（已修：500 字符 / [0,1]）
4. 事实 CRUD / forget / 工作流写操作的读-改-写竞态（已修：`mutate` + 引擎写锁）
5. `memory_tools.py` 缺 `import asyncio`（原无测试覆盖，运行时才炸）（已补）
6. `VectorStore` 本地模式不自建目录 → "unable to open database file"（已修：mkdir）
7. 蒸馏写对话级 store 绕过轨道根目录（users 轨潜在写错位置）（已修：轨道感知）

## 五、遗留问题（未动，按优先级）

1. **cloud_proxy / anthropic 供应商无 embeddings**：包装后会直连 `{base_url}/embeddings`
   得到 404/错误（改动前是即时 ProviderError）。两者净效果相同（无向量 + 警告日志），
   但若云网关未来提供 embeddings 端点则自动可用。可选优化：探测一次后本会话禁用。
2. **distill prompt 随事实数线性膨胀**（§⑤ 之前的备忘）：100 条事实 ≈ 5-7KB prompt。
   廉价解：注入 top-N（按置信度）。属蒸馏 LLM 侧，不在索引链路。
3. `save_data` 全量替换语义（17ms/次@100条）：百条规模无感，事实到数千条再增量化。
4. extractor 写路径在 `async_lock` 内跨 `await` 持有数据对象——与端点写路径已用
   同一 `asyncio.Lock` 串行化；与直接调用 `store.mutate` 的第三方代码理论上有
   窗口（当前无此类调用方）。
5. `ContextBuilder._relevant_fact_ids` 实例状态在并发 `build_context` 下互相覆盖
   （仅影响排序权重偶发失准，不影响正确性）。

## 六、如何复现

```bash
cd backend
.venv/Scripts/python.exe scripts/memory_verify.py     # 准确性：32 项断言
.venv/Scripts/python.exe scripts/memory_benchmark.py  # 速度：含改动前基线对照
.venv/Scripts/python.exe -m pytest tests/ -q          # 回归：203 passed
```

## 七、建议的提交划分（未提交，待审查后执行）

- **提交 1**：vector_store / vector_manager / memory_engine(接线部分) / extractor / chat_completions / memory/__init__ —— "修复向量索引协议错配与 N+1：批量协议接线+契约校验+连接复用+supersedes 收口+rebuild 清旧"
- **提交 2**：fact_manager / store / memory 端点 / context_service / memory_tools —— "记忆写入路径加速与原子化：分词预计算+中文双字词+读写锁"
