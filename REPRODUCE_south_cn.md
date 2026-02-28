复现步骤（实验）

范围：这份文件是给人/运维看的 checklist，用来在 Unix 机器上从头到尾把整个实验跑起来。

注意：repo 里的 install/deploy 脚本都是模板，你自己确认要跑才跑；不要默认直接执行。

1）准备环境

先开一个 Python venv（或用系统 Python），然后用 requirements.txt 把依赖装好。

2）配置服务端 .env

在 repo 根目录建一个 .env，最少要有：

- TELEGRAM_BOT_TOKEN
- REMINDER_ADMIN_TOKEN
- REMINDER_DB_PATH（可选，不写就用 ./data/reminders.sqlite3）
- REMINDER_API_HOST、REMINDER_API_PORT（可选）

3）启动服务（单进程实验模式）

用 src/app.py 一起跑 Telegram bot + HTTP API，然后确认 /health 回 ok。

4）绑定目标用户（Telegram）

目标用户要先跟 bot 讲一次 /start；系统会把（telegram user_id -> chat_id）存进 SQLite，之后才发得出提醒。

5）管理员代用户做 CRUD

在本机/客户端侧准备 CLI 的 env：

- REMINDER_API_BASE_URL
- REMINDER_BEARER_TOKEN（用 admin token）
- REMINDER_SCOPE_USER_ID（目标 telegram user_id）

然后用 reminderctl 做 create/list/update/delete。

6）可选：发放用户专属 token

管理员可以针对某个 user_id 发一个 token；目标用户之后就能用 Authorization: Bearer <user token> 去打 user endpoints，只能 CRUD 自己的提醒。

7）用例复现：房租提醒（整年）

参考 docs/usecase_tenant_rent_2026.md，里面有算好的整年时间表和对应的一串 reminderctl admin-create 命令。

8）刻意缺的那块（目前还没做）

现在这个实验有存 reminders，也能手动发消息，但还没有自动排程/worker 去：

- 定时扫 due 的 reminders
- 到点了就发 Telegram
- 发完把 done 标记掉

要让提醒真的自动触发，你需要再加一个很简单的 worker（cron/systemd timer 或一直跑的 loop），逻辑就是查 DB -> 发消息 -> 更新状态。
