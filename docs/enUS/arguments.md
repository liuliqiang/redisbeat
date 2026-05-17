## Init Policy

There are four init policies for restarting RedisBeat, defined in
[redisbeat/constants.py](../../redisbeat/constants.py). Select one by setting
`CELERY_REDIS_SCHEDULER_INIT_POLICY` in your Celery config.

- `INIT_POLICY_DEFAULT` (`"DEFAULT"`)
	- Default policy. If the scheduler was offline long enough to miss N
	  runs of a task, the task will fire N times after restart (one per
	  tick interval) until it catches up.
- `INIT_POLICY_RESET` (`"RESET"`)
	- Reset every task's `last_run_at` to the restart time, so the next
	  run is one full interval from now.
- `INIT_POLICY_FAST_FORWARD` (`"FAST_FORWARD"`)
	- Collapse all missed runs into a single immediate run, then resume
	  the normal cadence from the restart time.
- `INIT_POLICY_IMMEDIATELY` (`"IMMEDIATELY"`)
	- Fire every task immediately at restart and reset each task's
	  `last_run_at` to the restart time.
