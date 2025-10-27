# Supabase 邮件模板自定义配置

本目录包含 Supabase Auth (GoTrue) 的自定义邮件模板。

## 📋 模板列表

| 模板文件 | 用途 | 触发场景 |
|---------|------|---------|
| `confirmation.html` | 邮箱验证 | 用户注册后发送验证邮件 |
| `recovery.html` | 密码重置 | 用户请求重置密码 |
| `invite.html` | 用户邀请 | 管理员邀请新用户 |
| `magic_link.html` | 魔法链接登录 | 用户请求无密码登录 |
| `email_change.html` | 邮箱变更确认 | 用户更改邮箱地址 |

## 🎨 模板变量

所有模板都支持以下 Go 模板变量：

- `{{ .ConfirmationURL }}` - 验证/确认链接
- `{{ .Token }}` - 6 位数字验证码
- `{{ .TokenHash }}` - 哈希令牌
- `{{ .SiteURL }}` - 站点 URL
- `{{ .Email }}` - 用户邮箱地址
- `{{ .NewEmail }}` - 新邮箱地址（仅用于 email_change.html）

## 🔧 配置说明

### Docker Compose 配置

在 `docker-compose.yml` 的 `auth` 服务中：

```yaml
auth:
  environment:
    # 邮件模板路径配置
    GOTRUE_MAILER_TEMPLATES_CONFIRMATION: "file:///email_templates/confirmation.html"
    GOTRUE_MAILER_TEMPLATES_INVITE: "file:///email_templates/invite.html"
    GOTRUE_MAILER_TEMPLATES_RECOVERY: "file:///email_templates/recovery.html"
    GOTRUE_MAILER_TEMPLATES_MAGIC_LINK: "file:///email_templates/magic_link.html"
    GOTRUE_MAILER_TEMPLATES_EMAIL_CHANGE: "file:///email_templates/email_change.html"
  volumes:
    - ./volumes/email_templates:/email_templates:ro,z
```

### 应用配置更改

修改模板或配置后，需要重新创建容器：

```bash
# 重新创建 auth 服务容器
docker compose up -d auth

# 验证模板文件已挂载
docker exec supabase-auth ls -lh /email_templates/

# 验证环境变量
docker exec supabase-auth env | grep GOTRUE_MAILER_TEMPLATES
```

## 🧪 测试验证

### 1. 测试邮箱验证邮件 (confirmation.html)

在前端或通过 API 注册新用户：

```bash
curl -X POST 'http://localhost:8000/auth/v1/signup' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com",
    "password": "your-password"
  }'
```

### 2. 测试密码重置邮件 (recovery.html)

请求密码重置：

```bash
curl -X POST 'http://localhost:8000/auth/v1/recover' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com"
  }'
```

### 3. 测试魔法链接邮件 (magic_link.html)

请求魔法链接登录：

```bash
curl -X POST 'http://localhost:8000/auth/v1/magiclink' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com"
  }'
```

### 4. 查看日志

检查邮件发送日志：

```bash
# 查看 auth 服务日志
docker logs supabase-auth --tail 100 -f

# 过滤邮件相关日志
docker logs supabase-auth | grep -i "email\|mailer\|template"
```

## 📝 模板自定义指南

### HTML 模板结构

所有模板使用响应式 HTML + 内联 CSS 设计：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>邮件标题</title>
    <style>
        /* 内联样式确保邮件客户端兼容性 */
    </style>
</head>
<body>
    <!-- 邮件内容 -->
    <div class="container">
        <h1>{{ .ConfirmationURL }}</h1>
    </div>
</body>
</html>
```

### 设计原则

1. **响应式设计** - 使用 max-width: 600px 适配移动端
2. **内联样式** - 确保各种邮件客户端兼容
3. **清晰布局** - 重要操作使用醒目按钮
4. **双重保障** - 提供按钮和文本链接两种方式
5. **安全提示** - 包含安全警告和使用说明
6. **品牌一致** - 统一的视觉风格和色彩方案

### 颜色方案

| 模板 | 主色调 | 用途 |
|------|--------|------|
| confirmation | #3ecf8e (绿色) | 邮箱验证 |
| recovery | #f59e0b (橙色) | 密码重置 |
| invite | #8b5cf6 (紫色) | 用户邀请 |
| magic_link | #06b6d4 (青色) | 魔法链接 |
| email_change | #0ea5e9 (蓝色) | 邮箱变更 |

## ⚠️ 注意事项

1. **文件权限** - 模板文件挂载为只读 (`:ro`)
2. **编码格式** - 确保使用 UTF-8 编码
3. **Go 模板语法** - 使用 `{{ .Variable }}` 格式
4. **邮件客户端兼容性** - 测试多种邮件客户端显示效果
5. **SMTP 配置** - 确保 `.env` 中的 SMTP 设置正确

## 🔗 相关文档

- [Supabase Auth 官方文档](https://supabase.com/docs/guides/auth)
- [GoTrue 邮件模板配置](https://github.com/supabase/gotrue)
- [项目 SMTP 配置](.env)

## 📧 SMTP 配置检查

确保 `.env` 文件中的邮件配置正确：

```env
SMTP_ADMIN_EMAIL=your-email@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASS=your-smtp-password
SMTP_SENDER_NAME=Your App Name
```

## 🆘 故障排查

### 问题：模板未生效，仍使用默认邮件

**解决方案：**
1. 检查模板文件是否正确挂载：`docker exec supabase-auth ls /email_templates/`
2. 检查环境变量：`docker exec supabase-auth env | grep GOTRUE_MAILER_TEMPLATES`
3. 重新创建容器：`docker compose up -d auth`
4. 查看日志：`docker logs supabase-auth`

### 问题：邮件发送失败

**解决方案：**
1. 检查 SMTP 配置是否正确
2. 验证 SMTP 端口和加密方式
3. 确认 SMTP 授权码有效
4. 检查防火墙和网络连接

### 问题：模板变量未替换

**解决方案：**
1. 确保使用 Go 模板语法：`{{ .Variable }}`
2. 变量名大小写敏感，首字母大写
3. 检查模板文件 UTF-8 编码

## 📅 更新历史

- **2025-10-07** - 初始版本，创建 5 个邮件模板
