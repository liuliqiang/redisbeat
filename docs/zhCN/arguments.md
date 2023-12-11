## 初始化策略

RedisBeat 在  [redisbeat/constans.py]() 中定义了 4 种不同的初始化策略，分别为：

- INIT_POLICY_DEFAULT
	- RedisBeat 的默认策略，如果在重启期间你错过了 N 次执行，那么重启之后会补足这 N 次执行；
- INIT_POLICY_RESET
	- 在重启时将所有任务的开始计数时间重置为当前时间；
- INIT_POLICY_FAST_FORWARD
	- 如果在重启期间你错过了 N 次执行，那么重启之后只会执行一次，并且后续将按照正常周期计算；
- INIT_POLICY_IMMEDIATELY
	- 在重启后马上执行所有的任务，并且重置计数时间为当前时间；
