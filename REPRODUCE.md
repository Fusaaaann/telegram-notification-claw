# 管理员落地指南

这份文档面向管理员，目标不是解释实现细节，而是让你用最短路径把系统跑起来、绑定 Telegram、创建提醒并确认消息能发出去。

当前仓库有两种实际运行方式：

- 本地单进程模式：`src/app.py`
  - FastAPI API
  - Telegram Bot 轮询
  - 进程内调度器，每 60 秒检查一次到期提醒
- Vercel 模式：`api/index.py`
  - FastAPI API
  - Telegram Webhook 入口：`/v1/telegram/webhook`
  - 到期提醒需要主动调用 `POST /v1/admin/reminders/dispatch-due`

需要先知道的事实：

- 正常运行时使用 `ReminderDB.from_settings()`，底层始终走 `BlobStorage`
- `REMINDER_DB_PATH` 只是本地 SQLite 缓存路径，不是权威存储
- 本仓库里的本地测试会用 `LocalStorage`，但生产入口不会
- `scripts/` 下的脚本是辅助脚本，不是必经步骤

## 你能做什么

管理员接口使用：

```text
Authorization: Bearer <REMINDER_ADMIN_TOKEN>
```

管理员可以：

- 创建、查询、更新、删除提醒
- 创建全局提醒 `visibility=global`
- 创建指定用户提醒 `visibility=user`
- 给某个 Telegram 用户签发 user token
- 手动触发一次“发送到期提醒”

用户接口使用自己的 bearer token。管理员如果要操作某个用户范围内的提醒，必须额外带上：

```text
X-Reminder-User-Id: <正整数 user_id>
```

## 一条最短成功路径

如果你只想尽快验证系统是否可用，按这个顺序做：

1. 配置环境变量
2. 启动本地服务，或部署到 Vercel
3. 检查 `/health`
4. 为目标用户签发 token
5. 让该用户向机器人发送 `/start <user-token>`
6. 创建一个“现在就该触发”的提醒
7. 调用 `POST /v1/admin/reminders/dispatch-due`
8. 确认 Telegram 收到消息，且提醒被标记为 `done=true`

下面是完整步骤。

## 1. 前置条件

- Python 3.12+
- 一个来自 BotFather 的 Telegram Bot Token
- 已配置 Vercel Blob，并满足以下其一：
  - 环境变量里有 `BLOB_READ_WRITE_TOKEN`
  - 或显式设置 `REMINDER_BLOB_TOKEN`

安装依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 2. 环境变量

无论是本地模式还是 Vercel 模式，至少需要：

```bash
export TELEGRAM_BOT_TOKEN='...'
export REMINDER_ADMIN_TOKEN='admin-secret'
export BLOB_READ_WRITE_TOKEN='...'
```

可选变量：

- `REMINDER_BLOB_TOKEN`：显式覆盖 `BLOB_READ_WRITE_TOKEN`
- `REMINDER_BLOB_PATH`：Blob 对象路径，默认 `reminders.sqlite3`
- `REMINDER_BLOB_ACCESS`：`private` 或 `public`，默认 `private`
- `REMINDER_DB_PATH`：本地缓存文件路径，默认 `/tmp/reminders.sqlite3`
- `REMINDER_TIMEZONE`：解释无时区 `due_at` 时使用的时区，默认 `UTC`
- `REMINDER_API_HOST`：本地 API 绑定地址，默认 `0.0.0.0`
- `REMINDER_API_PORT`：本地 API 端口，默认 `8088`

认证规则：

- 管理员请求：`Authorization: Bearer <REMINDER_ADMIN_TOKEN>`
- 用户请求：`Authorization: Bearer <user token>`
- 管理员访问用户范围提醒：还要带 `X-Reminder-User-Id`

## 3. 本地运行

启动 API + Telegram polling + 调度器：

```bash
python3 -m src.app
```

预期行为：

- FastAPI 默认监听 `http://127.0.0.1:8088`
- Telegram Bot 会立即进入 polling
- 调度器每 60 秒检查一次到期提醒

健康检查：

```bash
curl http://127.0.0.1:8088/health
```

预期响应：

```json
{"ok":true}
```

## 4. Vercel 运行

部署时入口是 `api/index.py`，仓库里的 `vercel.json` 已经把请求路由到这里。

服务端至少需要这些环境变量：

- `TELEGRAM_BOT_TOKEN`
- `REMINDER_ADMIN_TOKEN`
- `BLOB_READ_WRITE_TOKEN` 或 `REMINDER_BLOB_TOKEN`

部署后先检查：

```bash
curl https://<deployment>/health
```

预期响应：

```json
{"ok":true}
```

然后把 Telegram webhook 指向部署地址：

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://<deployment>/v1/telegram/webhook"
```

注意：

- Vercel 模式只负责 webhook 收消息
- 到期提醒不会自动发出，必须通过 Cron 或外部调度调用 `POST /v1/admin/reminders/dispatch-due`

## 5. 给用户签发 token

管理员可以为某个 Telegram 用户 ID 签发一个 user token。

示例：给 `user_id=42` 签发 token

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  http://127.0.0.1:8088/v1/admin/users/42/token
```

预期响应结构：

```json
{"user_id":42,"token":"..."}
```

CLI 等价写法：

```bash
export REMINDER_API_BASE_URL='http://127.0.0.1:8088'
export REMINDER_BEARER_TOKEN="$REMINDER_ADMIN_TOKEN"
python3 -m cli.reminderctl admin-issue-user-token 42
```

## 6. 让用户绑定 Telegram 聊天

目标用户必须主动给机器人发送下面的命令：

```text
/start <user-token>
```

接受的形式：

- `/start <token>`
- `/start@BotName <token>`

不接受的形式：

- `/start`

成功时，机器人回复：

```text
ok, token linked; this chat will receive reminders.
```

如果没带 token，机器人回复：

```text
Missing start token. Use /start <user-token>.
```

这个动作会完成两件事：

- 从 `user_tokens` 找到对应的 `user_id`
- 把当前 `chat_id` 写入 `chat_bindings`

后续这个用户的提醒就会发到这个聊天里。

## 7. 以管理员身份创建提醒

### 全局提醒

全局提醒会在到期后广播到所有已绑定的 Telegram chat：

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"system maintenance","due_at":"2026-03-22T00:00:00Z","visibility":"global"}' \
  http://127.0.0.1:8088/v1/admin/reminders
```

### 用户提醒

用户提醒只属于指定用户，必须带 `X-Reminder-User-Id`：

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  -H "X-Reminder-User-Id: 42" \
  -H "Content-Type: application/json" \
  -d '{"text":"pay rent","due_at":"2026-03-22T00:00:00Z","visibility":"user"}' \
  http://127.0.0.1:8088/v1/admin/reminders
```

关键规则：

- CLI 里管理员创建提醒时，默认 `visibility="global"`
- 管理员创建或更新 `visibility="user"` 的提醒时，如果没有 `X-Reminder-User-Id`，请求会失败

CLI 示例：

```bash
export REMINDER_SCOPE_USER_ID=42
python3 -m cli.reminderctl admin-create "pay rent" --visibility user --due-at 2026-03-22T00:00:00
python3 -m cli.reminderctl admin-create "system maintenance" --visibility global --due-at +1d
```

CLI 的 `--due-at` 支持：

- `YYYY-MM-DD`
- `YYYY-MM-DDTHH:MM[:SS]`
- `now`
- `today`
- `tomorrow`
- `+Nd`、`+Nh`、`+Nm`、`+Nw`

如果只写日期，CLI 会自动补成 `09:00:00`。

## 8. 查询提醒

管理员查询时有一个容易踩坑的点：是否带 `X-Reminder-User-Id`，决定了你能看到什么。

不带 `X-Reminder-User-Id` 时，只返回全局提醒：

```bash
curl -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  http://127.0.0.1:8088/v1/admin/reminders
```

带 `X-Reminder-User-Id: 42` 时，返回：

- 全局提醒
- 用户 42 的用户级提醒

用户侧查询返回：

- 全局提醒
- 自己的用户级提醒

不会暴露其他用户的用户级提醒。

## 9. 用户自助操作

如果你也要顺便验证用户侧 CRUD，可以把刚签发的 user token 当 bearer token 使用：

```bash
export REMINDER_BEARER_TOKEN='<user-token>'
python3 -m cli.reminderctl user-create "buy milk" --due-at tomorrow
python3 -m cli.reminderctl user-list --include-done false
```

行为规则：

- 用户创建的提醒永远是 `visibility="user"`
- 用户只能更新或删除自己的用户提醒
- 用户列表里仍然会看到全局提醒

## 10. 手动触发到期提醒发送

### 本地模式

你可以：

- 等调度器自动醒来
- 或者直接调用 dispatch 接口，做一次确定性的发送测试

手动发送：

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  http://127.0.0.1:8088/v1/admin/reminders/dispatch-due
```

预期响应结构：

```json
{
  "ok": true,
  "scanned": 2,
  "due": 2,
  "sent": 2,
  "skipped_unbound": 0,
  "invalid_due_at": [],
  "failed": []
}
```

发送规则来自当前代码实现：

- `due_at <= now` 就会被视为到期
- 带时区的时间会先转换成 UTC
- 不带时区的时间会按 `REMINDER_TIMEZONE` 解释
- `due_at` 非法的提醒不会被标记完成，其 ID 会出现在 `invalid_due_at`
- 只有成功发出后，提醒才会被标记为 `done=true`
- 用户提醒如果没有绑定 chat，会增加 `skipped_unbound`
- 全局提醒会按去重后的 `chat_id` 各发一次

### Vercel 模式

Vercel 不会仅靠 webhook 自动发送到期提醒，你必须：

- 用 Vercel Cron 调用这个接口，或
- 用其他调度系统调用这个接口

## 11. 最小验收用例

推荐用下面顺序做一次完整验收：

1. 启动本地服务或完成 Vercel 部署
2. 调用 `/health` 确认服务存活
3. 为用户 `42` 签发 token
4. 让目标 Telegram chat 给机器人发送 `/start <token>`
5. 创建一个“现在或过去时间”的用户提醒
6. 调用 `POST /v1/admin/reminders/dispatch-due`
7. 确认三件事：
   - Telegram 收到了提醒文本
   - dispatch 响应里的 `sent` 增加了
   - 数据里的该提醒已经变成 `done=true`

## 12. 常见问题

- `TELEGRAM_BOT_TOKEN` 为空时，手动 dispatch 会返回 HTTP 500
- `REMINDER_ADMIN_TOKEN` 为空时，管理员接口会返回 HTTP 500
- `Authorization` 缺失或错误时，受保护接口返回 HTTP 401
- `X-Reminder-User-Id` 格式错误时，管理员用户范围接口返回 HTTP 400
- 通过管理员接口读取用户提醒时，如果没带匹配的 `X-Reminder-User-Id`，访问会失败
- 在 Vercel 模式下，持久化依赖 Blob；只有 `/tmp` 不能保证数据持久

## 管理员快速抄作业

如果你要把系统从 0 拉起并完成一次真实发送，最常用的命令就是这些：

```bash
# 1. 启动本地服务
python3 -m src.app

# 2. 健康检查
curl http://127.0.0.1:8088/health

# 3. 签发 user token
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  http://127.0.0.1:8088/v1/admin/users/42/token

# 4. 创建用户提醒
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  -H "X-Reminder-User-Id: 42" \
  -H "Content-Type: application/json" \
  -d '{"text":"pay rent","due_at":"2026-03-22T00:00:00Z","visibility":"user"}' \
  http://127.0.0.1:8088/v1/admin/reminders

# 5. 手动触发发送
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  http://127.0.0.1:8088/v1/admin/reminders/dispatch-due
```
