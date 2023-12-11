## Init Policy

There four type init policy for restart RedisBeat，which defined at [redisbeat/constans.py]()：

- INIT_POLICY_DEFAULT
	- Default policy for RedisBeat, If you miss N times run during your restart, your task will run N times after restart.
- INIT_POLICY_RESET
	- Reset all task's last run time to restart time.
- INIT_POLICY_FAST_FORWARD
	- If you miss N times run during your restart, your task will only run ONCE after restart and continue from curr time.
- INIT_POLICY_IMMEDIATELY
	- Run all task immediately, and reset all task's last run time as curr restart time.
