# 密码找回功能说明

## 功能概述

本系统提供了完整的密码找回功能，包括以下步骤：

1. **发送重置邮件** - 用户输入邮箱地址，系统发送包含验证码的邮件
2. **验证验证码** - 用户输入收到的验证码进行验证
3. **重置密码** - 验证成功后，用户设置新密码

## API 端点

### 1. 发送密码重置邮件
```
POST /recall
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**响应：**
```json
{
  "msg": "密码重置邮件已发送，请检查您的邮箱",
  "email": "user@example.com"
}
```

### 2. 验证重置验证码
```
POST /recall/verify
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456"
}
```

**响应：**
```json
{
  "msg": "验证码验证成功",
  "verified": true,
  "email": "user@example.com"
}
```

### 3. 重置密码
```
POST /recall/reset
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "newpassword123"
}
```

**响应：**
```json
{
  "msg": "密码重置成功，请使用新密码登录"
}
```

## 配置要求

### 环境变量
在运行应用前，请设置以下环境变量：

```bash
# Supabase 配置
export SUPABASE_URL=http://localhost:8000
export SUPABASE_ANON_KEY=your-anon-key
export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# 前端URL（用于邮件重定向）
export FRONTEND_URL=http://localhost:3000
```

### Supabase 配置
1. 确保 Supabase 项目已启用邮件功能
2. 配置邮件模板（可选）
3. 设置适当的邮件重定向URL

## 安全特性

1. **验证码验证** - 重置密码前必须验证邮箱验证码
2. **错误信息保护** - 不暴露具体的系统错误信息
3. **管理员权限** - 密码重置需要管理员权限
4. **日志记录** - 记录所有密码重置操作

## 使用流程

### 前端实现建议

1. **第一步：输入邮箱**
   - 用户输入邮箱地址
   - 调用 `/recall` 端点
   - 显示"邮件已发送"提示

2. **第二步：输入验证码**
   - 用户输入收到的验证码
   - 调用 `/recall/verify` 端点
   - 验证成功后显示密码输入框

3. **第三步：设置新密码**
   - 用户输入新密码
   - 调用 `/recall/reset` 端点
   - 显示成功消息并跳转到登录页面

### 错误处理

- 验证码错误或过期
- 邮箱不存在
- 网络错误
- 服务器错误

## 注意事项

1. **服务角色密钥** - 确保 `SUPABASE_SERVICE_ROLE_KEY` 已正确配置
2. **邮件配置** - 确保 Supabase 邮件服务正常工作
3. **前端URL** - 确保邮件重定向URL配置正确
4. **生产环境** - 生产环境中请使用 HTTPS 和安全的 cookie 设置

## 测试

可以使用以下命令测试API：

```bash
# 发送重置邮件
curl -X POST http://host.docker.internal:8001/recall \
  -H "Content-Type: application/json" \
  -d '{"email": "2021020024@email.szu.edu.cn"}'

# 验证验证码
curl -X POST http://host.docker.internal:8001/recall/verify \
  -H "Content-Type: application/json" \
  -d '{"email": "2021020024@email.szu.edu.cn", "code": "123456"}'

# 重置密码
curl -X POST http://host.docker.internal:8001/recall/reset \
  -H "Content-Type: application/json" \
  -d '{"email": "2021020024@email.szu.edu.cn", "code": "123456", "new_password": "newpass123"}'
```
