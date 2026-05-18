## 初始化策略

RedisBeat 在 [redisbeat/constants.py](../../redisbeat/constants.py) 中定义了 4 种初始化策略，
通过设置 Celery 配置项 `CELERY_REDIS_SCHEDULER_INIT_POLICY` 来选择：

- `INIT_POLICY_DEFAULT`（`"DEFAULT"`）
	- 默认策略。如果调度器停机期间错过了 N 次执行，重启之后任务会按 tick 间隔
	  连续触发 N 次，直到追平。
- `INIT_POLICY_RESET`（`"RESET"`）
	- 重启时将所有任务的 `last_run_at` 重置为当前时间，下次执行从一个完整周期之后开始。
- `INIT_POLICY_FAST_FORWARD`（`"FAST_FORWARD"`）
	- 把错过的多次执行合并为一次立即执行，之后从当前时间继续正常周期。
- `INIT_POLICY_IMMEDIATELY`（`"IMMEDIATELY"`）
	- 重启后立刻触发所有任务，并把每个任务的 `last_run_at` 重置为当前时间。
