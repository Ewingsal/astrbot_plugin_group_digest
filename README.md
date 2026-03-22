# astrbot_plugin_group_digest

群聊兴趣日报与主动互动插件（LLM 语义分析 + 每日定时主动发言）。

## 当前能力

- `/group_digest`：统计“昨天全天”的群聊兴趣日报。
- `/group_digest_today`：统计“今天 00:00 到当前时刻”的群聊兴趣日报。
- `/group_digest_debug_today`：今日底层调试统计（消息总数/参与成员/活跃榜）。
- 每日固定时间主动发言：按群独立分析“当天 00:00 到触发时刻”，仅发送 `suggested_bot_reply`。

## 处理链路

- 规则统计负责：总发言数、参与成员数、活跃成员排行、统计范围。
- LLM 语义分析负责：热门话题、成员兴趣摘要、整体总结、建议 Bot 主动发言。
- 定时主动发送直接复用同一日报分析链路中的 `suggested_bot_reply`，不走第二套文案逻辑。
- 当前实现会在一次 LLM 调用中同时返回 `group_topics`、`member_interests`、`overall_summary`、`suggested_bot_reply`，减少调度耗时。
- 日报已接入缓存池：命令与 scheduler 入口都会先查缓存，命中时直接复用，不再重复走 LLM。

## 日报缓存机制（MVP）

- 只要日报成功生成，无论来源是命令还是 scheduler，都会写入缓存。
- 缓存命中条件：同群、同日、同模式（`yesterday` / `today` / `scheduled`）、关键配置一致、且无新消息。
- 若检测到有新消息或配置变化，则触发全量重算并覆盖缓存。
- 当前版本先做“命中复用 / 失效重算”，暂不做“旧日报 + 新消息”的复杂增量更新。
- 插件自有消息会被排除，不纳入日报统计、语义分析输入和缓存失效判断：
- 控制命令：`/group_digest`、`/group_digest_today`、`/group_digest_debug_today`
- 完整日报输出（默认前缀 `群聊兴趣日报（`）与调试输出前缀
- 可识别为 bot sender 的插件自发消息（用于避免主动发言回流污染）

## LLM Provider 选择逻辑

1. `use_llm_topic_analysis=false`：不调用 LLM，仅输出统计结果，并提示语义分析已关闭。
2. 配置了 `analysis_provider_id`：优先使用该 provider。
3. 未配置 `analysis_provider_id`：复用当前会话模型（`get_current_chat_provider_id(umo=event.unified_msg_origin)`）。
4. provider 不可得或模型失败：
- `fallback_to_stats_only=true`：降级为仅统计。
- `fallback_to_stats_only=false`：返回清晰错误提示。

## 定时主动发言规则

- 仅支持群聊（私聊不会进入定时主动发言范围）。
- 必须先记录到该群的 `unified_msg_origin`，该群才会成为定时候选目标。
- 调度触发时会遍历所有已记录群，按群独立执行：
- 群 A 只分析群 A 消息，并发回群 A。
- 群 B 只分析群 B 消息，并发回群 B。
- 可选白名单：启用后仅对白名单群执行。
- 只发送 `suggested_bot_reply`，不发送整份日报。

## 存储位置

默认都在 AstrBot `data` 目录下（相对路径自动拼接到 data）：

- `storage_path = plugin_data/astrbot_plugin_group_digest/messages.json`
- `group_origin_storage_path = plugin_data/astrbot_plugin_group_digest/group_origins.json`
- `report_cache_path = plugin_data/astrbot_plugin_group_digest/report_cache.json`

可通过 `astrbot_data_dir` 显式指定 data 根目录。

## 配置项（重点）

### 日报与 LLM

- `use_llm_topic_analysis`
- `analysis_provider_id`
- `analysis_prompt_template`
- `interaction_prompt_template`
- `max_messages_for_analysis`
- 用于控制送入 LLM 的消息条数上限。默认 `80`，调小可降低延迟，调大可提升覆盖面。
- `fallback_to_stats_only`
- `report_cache_path`

### 定时主动发言

- `enable_scheduled_proactive_message`：是否启用定时主动发言（默认 `false`）。
- `scheduled_send_hour`：触发小时（默认 `18`）。
- `scheduled_send_minute`：触发分钟（默认 `0`）。
- `scheduled_mode`：当前仅支持 `today_until_scheduled_time`。
- `store_group_origin`：是否记录群会话标识（默认 `true`）。
- `scheduled_group_whitelist_enabled`：是否启用白名单（默认 `false`）。
- `scheduled_group_whitelist`：白名单群 ID 列表。
- `scheduled_send_timezone`：调度时区（默认 `Asia/Shanghai`）。

## 快速联调（无需等到 18:00）

1. 先启用 `enable_scheduled_proactive_message=true`。
2. 将 `scheduled_send_hour` / `scheduled_send_minute` 改成当前时间后几分钟。
3. 在两个测试群都发几条消息（确保插件记录各自 `unified_msg_origin`）。
4. 观察日志：会看到遍历群列表、白名单过滤、逐群生成分析、逐群发送结果。
5. 验证两个群收到的主动发言文案不同且不串群。

## 缓存联调建议

1. 在同一群连续执行两次 `/group_digest_today`（中间不发新消息），第二次应命中 `cache_hit`。
2. 再发一条新消息后执行 `/group_digest_today`，应出现 `cache_refresh` 并重算。
3. 观察 scheduler 日志，确认 `source=scheduler` 的 `cache_write` 也会出现。

## 依赖与测试

- `requirements.txt`：运行时依赖（当前无额外第三方依赖）。
- `requirements-dev.txt`：开发与测试依赖（pytest）。

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

## AstrBot API 适配说明

- 主动发送基于官方能力：`self.context.send_message(unified_msg_origin, chain)`。
- 定时任务基于官方建议：在插件 `__init__` 中用 `asyncio.create_task(...)` 启动后台任务。
- 若 AstrBot 后续调整接口签名，请在 `services/scheduler_service.py` 的发送适配层更新（已保留 TODO）。
