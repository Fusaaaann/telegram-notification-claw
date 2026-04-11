# 复现指南

1. 要先准备什么账号
2. 每个平台要配什么变量
3. 怎么一键部署
4. 怎么在 Telegram 里真正收到提醒

## 1. 先准备的账号

只需要两个平台：

- Telegram
  - 你自己的 Telegram 账号
  - 到 `@BotFather` 创建一个 Bot
  - 记下 Bot Token，后面填到 `TELEGRAM_BOT_TOKEN`
- Vercel
  - 一个 Vercel 账号
  - 一个已连接到本仓库的 Vercel Project
  - 在这个 Project 里开通 Blob Storage

## 2. 每个平台要配置什么

### Telegram / BotFather

这里只需要拿到：

- `TELEGRAM_BOT_TOKEN`

部署完成后，还要做一次 webhook 绑定：

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://<your-domain>/v1/telegram/webhook"
```

### Vercel

在 Project 的 Environment Variables 里至少配置：

- `TELEGRAM_BOT_TOKEN`
- `REMINDER_ADMIN_TOKEN`
- `BLOB_READ_WRITE_TOKEN`

可选：

- `REMINDER_BLOB_TOKEN`
  - 如果你想显式覆盖 `BLOB_READ_WRITE_TOKEN`
- `REMINDER_TIMEZONE`
  - 不填时默认是 `UTC`

说明：

- `BLOB_READ_WRITE_TOKEN` 一般在你创建 Vercel Blob 后就会自动提供
- `REMINDER_ADMIN_TOKEN` 你自己定义一个管理员口令即可，比如随机长字符串

## 3. 一键部署

仓库已经带了部署脚本。

首次使用前先完成一次：

```bash
vercel login
vercel link
```

然后直接部署：

```bash
./scripts/deploy_vercel.sh
```

Windows PowerShell：

```powershell
./scripts/deploy_vercel.ps1
```

部署完成后先检查服务是否正常：

```bash
curl https://<your-domain>/health
```

预期返回：

```json
{"ok":true}
```

## 4. 怎么在 Telegram 里收到提醒

最短成功路径就是下面 5 步。

### 第 1 步：给目标用户签发 token

假设目标用户 ID 是 `42`：

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  https://<your-domain>/v1/admin/users/42/token
```

你会拿到：

```json
{"user_id":42,"token":"<user-token>"}
```

### 第 2 步：让这个用户在 Telegram 里发送绑定命令

用户打开你的 Bot，对 Bot 发送：

```text
/start <user-token>
```

预期机器人回复：

```text
ok, token linked; this chat will receive reminders.
```

这一步成功后，这个聊天窗口就绑定好了，后续提醒会发到这里。

### 第 3 步：创建一个马上到期的提醒

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  -H "X-Reminder-User-Id: 42" \
  -H "Content-Type: application/json" \
  -d '{"text":"pay rent","due_at":"2026-04-11T00:00:00Z","visibility":"user"}' \
  https://<your-domain>/v1/admin/reminders
```

`due_at` 只要填一个“现在之前”的时间，就会被视为已到期。

### 第 4 步：手动触发发送

```bash
curl -X POST \
  -H "Authorization: Bearer $REMINDER_ADMIN_TOKEN" \
  https://<your-domain>/v1/admin/reminders/dispatch-due
```

### 第 5 步：确认结果

预期你会看到两件事：

- Telegram 里马上收到 `pay rent`
- dispatch 返回结果里的 `sent` 大于 `0`

如果这两件事都成立，说明部署、绑定、提醒发送都正常。

## 5. 日常使用方式

以后给某个用户发提醒，重复下面流程即可：

1. 先确保用户已经做过一次 `/start <user-token>` 绑定
2. 用管理员接口为这个用户创建 reminder
3. 调用 `/v1/admin/reminders/dispatch-due`

如果你想自动发送到期提醒，再给 Vercel Cron 加一个定时调用：

- `POST /v1/admin/reminders/dispatch-due`

就够了。
