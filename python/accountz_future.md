# accountz 演进设计：公司统一账号系统

> 基于 `python/accountz.py`（账号存储库：sqlite / mysql / mongo 三后端）演进为
> 服务公司内多个中型互联网产品和游戏产品的统一账号系统（只存身份，不存业务数据）。
>
> 撰写日期：2026-09-21

---

## 1. 现状与目标

### 现状

`accountz.py` 是一个**嵌入式账号存储库**：

- 每个产品各自 import 该库、直连数据库
- 身份字段（uid/urs/pass/mail/mobile）与业务字段（level/exp/gold/credit/消费流水）混在一张表
- 三后端一致性维护成本高（大量代码在处理 sqlite/mysql/mongo 行为差异）
- 密码按传入值原样存储，哈希由外层决定
- 单 MySQL 连接 + RLock 全局串行化

### 目标形态

**中心化的统一账号服务**：

- 各产品只调 API（HTTP/gRPC），永远不直连账号库
- 只管身份认证与账号关系，不存任何业务数据
- 多产品接入、跨产品识别同一用户、SSO 免登
- 标准协议（OAuth 2.0 / OIDC），各产品用现成客户端库接入

### 定位跃迁

| | 现在 | 目标 |
|---|---|---|
| 形态 | Python 库，进程内调用 | 独立服务，网络 API |
| 数据边界 | 所有产品共享一张表 | 产品只见自己的 open_id |
| 后端 | sqlite/mysql/mongo 三选 | 收敛为 MySQL 主库 + Redis |
| 密码 | 调用方决定哈希 | 服务端统一 argon2id |
| 协议 | 无（函数调用） | OAuth 2.0 + OIDC |

后端收敛说明：sqlite 保留给本地开发测试；mongo 后端退役——三后端一致性是
当前库最大的维护负担，服务化后没有理由继续背。

---

## 2. 数据模型

### 2.1 表总览

四张核心表，分工如下：

| 表 | 回答的问题 |
|---|---|
| `account` | "这个人是谁？"——纯粹的身份主体（瘦身后） |
| `apps` | "谁能来调我？"——接入产品注册与凭证 |
| `identifiers` | "这个登录凭据是谁？"——N 种登录方式 → 1 个 uid |
| `user_app` | "这个人在这个产品里叫什么、能不能进？"——uid → per-app open_id + 应用级状态 |

四张表合起来是微信开放平台 union_id/open_id 模型的自建版：
全局 `uid` 天然承担 union_id 语义。

### 2.2 account（瘦身版）

最终形态 DDL（MySQL，utf8mb4，时间统一 UTC）：

```sql
CREATE TABLE account (
    uid           BIGINT PRIMARY KEY AUTO_INCREMENT,
    pass          VARCHAR(98) NOT NULL DEFAULT '',   -- argon2id 哈希（服务端统一算法）
    name          VARCHAR(32) NOT NULL DEFAULT '',   -- 昵称
    status        TINYINT NOT NULL DEFAULT 0,        -- 见下方值域
    gender        TINYINT NOT NULL DEFAULT 0 CHECK (gender IN (0, 1, 2)),
    birthday      DATE,
    mail          VARCHAR(88),                       -- 联系邮箱（登录用邮箱在 identifiers）
    mobile        VARCHAR(32),                       -- 联系手机（登录用手机在 identifiers）
    src           VARCHAR(16),                       -- 注册来源产品 app_id
    reg_ip        VARCHAR(70),                       -- 注册 ip（支持 IPv6）
    last_ip       VARCHAR(70),                       -- 最近登录 ip
    reg_date      DATETIME NOT NULL,                 -- 注册时间（UTC）
    last_login    DATETIME,                          -- 最近登录时间（UTC）
    login_times   BIGINT NOT NULL DEFAULT 0 CHECK (login_times >= 0),
    mfa_enabled   TINYINT NOT NULL DEFAULT 0,        -- 0=未开启 1=TOTP
    mfa_secret    VARCHAR(64),                       -- TOTP 密钥（加密存储）
    realname      TINYINT NOT NULL DEFAULT 0,        -- 实名状态 0=未认证 1=成年 2=未成年
    misc          TEXT,                              -- JSON 扩展字段
    version       BIGINT NOT NULL DEFAULT 0,         -- 乐观锁：敏感变更 +1，token 校验可带版本
    updated_at    DATETIME NOT NULL                  -- 最近修改时间（UTC）
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

要点说明：

- **urs/cid 列废弃**：登录名迁到 `identifiers`；外部 uid 语义被 per-app
  `open_id` 取代
- **mail/mobile 双轨**：account 表存"联系方式"（找回密码、通知用），
  identifiers 表存"能否用它登录"（verified=1 才行）；两者独立演进，
  换绑手机不影响登录标识，反之亦然
- **ip 拆成 reg_ip/last_ip**：注册 ip 有风控与审计价值，不应被登录覆盖
- **realname**：游戏防沉迷依赖实名状态（具体实名数据对接第三方，
  这里只存结论），成年/未成年直接影响各游戏的宵禁与充值限额策略
- **mfa_***：TOTP 二步验证的落点，服务内部产品和高价值账号可开启
- **version**：改密/封禁/MFA 变更时 +1；已签发的 JWT 里带签发时的
  version，校验时发现库中 version 更新则拒绝——实现"改密即踢下线"
  而不必维护全量 token 黑名单
- 沿用现有设计的合理部分：pass 列宽 98（容纳 argon2id 哈希）、
  gender CHECK 值域、login_times 非负约束、misc 存 JSON 文本
- 列名统一小写下划线（现表的 `RegDate/LastLoginDate/LoginTimes` 混用
  驼峰，趁 schema 重做时归一）

`status` 值域扩展（现在的 0/1 太窄）：

```
0 = 正常
1 = 全局封禁（所有产品拒绝登录）
2 = 冻结（用户自主申请或风控临时冻结）
3 = 待注销（冷静期，个保法合规要求）
4 = 已注销
```

时间字段改存 **UTC**（现设计说明第 8 条的"机房本地时间"在跨产品跨地域
统一服务下是长期隐患，趁早改）。

### 2.3 apps —— 应用注册表

每个产品一行，由账号系统管理员录入，不是用户数据。

```sql
CREATE TABLE apps (
    app_id        VARCHAR(16)  PRIMARY KEY,        -- 如 'game-a'，或自增整数
    app_secret    VARCHAR(64)  NOT NULL,           -- 服务端调用凭证（哈希存储）
    name          VARCHAR(64)  NOT NULL,           -- 产品名
    redirect_uris TEXT,                            -- OIDC 回调地址白名单（JSON 数组）
    status        TINYINT NOT NULL DEFAULT 0,      -- 0=启用 1=停用
    created_at    DATETIME NOT NULL
);
```

### 2.4 identifiers —— 登录标识表

一个 uid 可以有多行（多种登录方式），支持用户名/邮箱/手机号/第三方混合登录。

```sql
CREATE TABLE identifiers (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    uid        BIGINT NOT NULL,                    -- 指向 account.uid
    id_type    VARCHAR(16) NOT NULL,               -- 'urs'/'mail'/'mobile'/'wechat'/'qq'/'apple'
    id_value   VARCHAR(128) NOT NULL,              -- 登录名/邮箱/手机号/第三方 openid
    verified   TINYINT NOT NULL DEFAULT 0,         -- 是否已验证（邮箱/短信/第三方授权即验证）
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_type_value (id_type, id_value),  -- 同一类型下标识全局唯一
    KEY idx_uid (uid)
);
```

### 2.5 user_app —— 用户-应用绑定表

用户在某产品首次登录/授权时产生。

```sql
CREATE TABLE user_app (
    uid         BIGINT NOT NULL,
    app_id      VARCHAR(16) NOT NULL,
    open_id     VARCHAR(32) NOT NULL,              -- 该用户在此应用内的脱敏 ID
    status      TINYINT NOT NULL DEFAULT 0,        -- 0=正常 1=此应用内封禁
    first_login DATETIME NOT NULL,
    last_login  DATETIME,
    PRIMARY KEY (uid, app_id),
    UNIQUE KEY uk_app_openid (app_id, open_id)
);
```

封禁语义分层：

- **全局封禁**：改 `account.status`，所有产品 token 校验统一拒绝
- **单产品封禁**：只改 `user_app.status`，不影响公司其他产品
  （某游戏封号不应该波及公司内部工具或其他游戏）

---

## 3. open_id 设计

### 3.1 要求

- 不可逆推出 uid
- 同一用户在不同 app 下的 open_id 完全不同（无法跨产品撞库关联）
- 稳定不变（同一用户在同一 app 永远是同一个值）

### 3.2 生成方式

```
open_id = HMAC-SHA256(app 独立密钥, uid) 取前 16 字节的 hex 编码（32 字符）
```

- 每个 app 一把独立密钥 → 游戏 A 和游戏 B 对同一 uid 算出的 open_id 毫无关联
- 账号服务持有全部密钥 → 可随时从 open_id 反查 uid（或直接查 user_app 表）
- 纯函数计算，生成无需查库、无需发号器，天然幂等，并发无冲突
- 可选：带 app 前缀提升可读性，如 `ga_x8f3a2...`（ga = game A）

### 3.3 为什么用字符串而不是自增整数

open_id 是**暴露给外部产品**的标识，自增整数有四个致命问题：

1. **泄露业务情报**：竞对注册两个账号，看 open_id 差值即知新增用户量；
   拿到 open_id=50000 即知总用户量级。典型的序列号枚举漏洞
   （OWASP 有专门条目）。微信/Google/GitHub 的对外 ID 全是不可枚举字符串
2. **跨产品不可关联性做不到**：即使每个 app 从不同起点自增，注册顺序仍然
   相关——A 里 open_id 相邻的两个人在 B 里大概率也相邻，数据分析可串联
   两个产品的用户
3. **可被枚举遍历**：即使做偏移混淆，攻击者可遍历撞库；HMAC 输出不可逆
4. **生成有中心化瓶颈**：自增依赖数据库序列或发号器；HMAC 任何服务实例都能算

原则：**自增整数是好的内部主键，是坏的外部标识**。

| | 暴露范围 | 类型 | 理由 |
|---|---|---|---|
| `uid` | 仅账号服务内部 | 自增 int64 | 紧凑、可排序、JOIN 高效 |
| `open_id` | 交给各产品 | HMAC 字符串 | 防枚举、防关联、防反推 |

---

## 4. 核心流程

### 4.1 注册

```
1. account 表插入一行 → 得到全局 uid
2. identifiers 插入 (uid, 'urs', 登录名, verified=1)
   —— 手机号注册则插 (uid, 'mobile', '138...', verified=1)
3. user_app 插入 (uid, 当前app_id, open_id, first_login=now)
   —— 注册总是发生在某个具体产品里
```

### 4.2 密码登录

```
1. 用户提交 (登录标识, 密码, app_id)
2. SELECT uid FROM identifiers WHERE id_type=? AND id_value=?
   —— id_type 可自动探测：含 @ 按 mail，纯数字按 mobile，否则 urs
3. 取 account 表验证密码（argon2id verify，不再 WHERE pass=? 匹配）、查全局 status
4. 查/插 user_app：
   - 无 (uid, app_id) 行 → 首次登录此产品，自动建绑定，生成 open_id
   - 有 → 检查 user_app.status（应用级封禁），更新 last_login
5. 签 token，claims 放 { sub=open_id, app_id }（uid 仅内部流转）
6. 返回给产品的用户标识是 open_id，产品拿它建自己的业务档案
```

### 4.3 第三方登录（以微信为例）

```
1. 微信 OAuth 回调 → 拿到微信侧 openid
2. SELECT uid FROM identifiers WHERE id_type='wechat' AND id_value=openid
3. 命中 → 走密码登录流程第 3 步起
   未命中 → 让用户绑定已有账号（验一次密码）或新建账号，
            然后 identifiers 插 (uid, 'wechat', openid)
4. 同一人先绑微信又绑手机 → identifiers 两行指向同一 uid，天然打通
```

### 4.4 跨产品识别（仅限账号服务内部）

游戏 B 想知道"我这个玩家在游戏 A 是谁"是**不允许的**——各产品只见自己的
open_id。打通只在账号服务内部发生：

```sql
-- 运营后台/风控查某人在所有产品的活跃情况：
SELECT app_id, first_login, last_login, status FROM user_app WHERE uid = ?;
```

---

## 5. 认证协议：OAuth 2.0 + OIDC

不自造 session 机制，直接以标准协议对外：

- **登录**：授权码模式（Web SSO）；游戏客户端/移动端用授权码 + PKCE；
  TV/主机类可用设备码模式
- **令牌**：
  - access_token：JWT，短时效（5~15 分钟）
  - refresh_token：落 Redis/DB，可撤销
  - token 黑名单：支撑封禁即时生效
- **用户信息**：标准 `userinfo` 端点，按 scope 返回字段
- **第三方登录**：账号服务自己做微信/QQ/Apple/Google 的 OAuth 客户端，
  绑定到统一 uid——各产品不需要每家都接一遍
- **SSO**：统一登录页 + 单点登出，协议自带，无需发明

好处：各产品用现成的 OIDC 客户端库接入，不必为自造协议写 N 个语言的 SDK。

---

## 6. HTTP API 设计

API 分四个平面，各自鉴权方式不同：

| 平面 | 调用方 | 鉴权 | 阶段 |
|---|---|---|---|
| 私有 API `/v1/*` | 各产品服务端 / 产品内嵌 SDK | 服务签名 或 用户 Bearer token | 阶段 2 |
| OIDC 端点 `/oauth2/*` | 用户浏览器 / 标准客户端库 | 协议内置 | 阶段 3 |
| 内省端点 `/v1/introspect` | 各产品服务端 | 服务签名 | 阶段 2 |
| 管理端点 `/v1/admin/*` | 运营后台 | 服务签名 + 员工身份，全量审计 | 阶段 4 |

### 6.1 通用约定

- JSON + UTF-8，路径带版本号 `/v1/`
- **服务签名**（产品服务端调用）：请求头
  `X-App-Id` / `X-Timestamp` / `X-Nonce` / `X-Signature`，
  其中 `X-Signature = HMAC-SHA256(app_secret, method + path + timestamp + nonce + body_sha256)`；
  timestamp 偏差超 5 分钟或 nonce 重放（Redis 记 5 分钟窗口）一律拒绝
- **用户令牌**：`Authorization: Bearer <access_token>`（JWT，claims 含
  `sub=open_id, app_id, ver=account.version`）
- 统一错误格式：

```json
{ "code": 40101, "message": "invalid credential", "request_id": "req_8f3a2b" }
```

  错误码分段：`400xx` 参数/校验，`401xx` 认证，`403xx` 封禁/权限，
  `404xx` 不存在，`409xx` 冲突（标识已占用），`429xx` 限流，`500xx` 内部错误
- 写操作支持 `Idempotency-Key` 请求头（注册/发码等重试安全）
- 所有请求分配 `request_id`，落访问日志与审计日志，便于跨系统排查

### 6.2 私有 API（阶段 2，产品接入的主通道）

#### 认证与会话

```
POST /v1/auth/login            密码直登（游戏/移动端无浏览器场景）
POST /v1/auth/logout           登出：撤销当前 refresh_token
POST /v1/auth/refresh          用 refresh_token 换新 access_token
```

`POST /v1/auth/login` 请求/响应示例：

```json
// 请求（服务签名 + 用户凭据）
{
    "identifier": "alice@example.com",   // 登录名/邮箱/手机号，服务端自动探测类型
    "password": "...",                    // TLS 内明文；前端可选 RSA 预加密
    "device_id": "d-9f8e...",             // 风控用，可选
    "ip": "1.2.3.4"                       // 产品服务端透传真实用户 ip
}

// 200 响应
{
    "access_token": "eyJ...",             // JWT，5~15 分钟
    "refresh_token": "rt_...",            // 30 天，可撤销
    "expires_in": 900,
    "open_id": "ga_x8f3a2...",            // 该产品内用户标识
    "profile": { "name": "alice", "gender": 2, "realname": 1 }
}

// 403 响应（封禁时明确告知，供产品提示用户）
{ "code": 40301, "message": "account banned", "scope": "global" }
```

登录失败统一返回 `40101 invalid credential`——**不区分"用户不存在"和
"密码错误"**，防止账号枚举；MFA 开启时返回 `200 + mfa_required + 临时票据`，
客户端再调 `POST /v1/auth/mfa` 提交 TOTP 码完成登录。

#### 注册与账号

```
POST   /v1/users                      注册（identifier + password + app_id）
GET    /v1/users/me                   当前用户资料（按 token 的 scope 过滤字段）
PATCH  /v1/users/me                   改资料（name/gender/birthday/misc）
POST   /v1/users/me/password          改密码（old + new；成功后 version+1，
                                      所有已签发 token 失效 = 全端下线）
POST   /v1/users/me/delete            申请注销（进入冷静期，status=3）
DELETE /v1/users/me/delete            撤销注销申请（冷静期内）
```

#### 登录标识管理（identifiers 表的 API 面）

```
GET    /v1/users/me/identifiers             列出已绑定的登录方式
POST   /v1/users/me/identifiers             绑定新标识（需验证码或密码确认）
DELETE /v1/users/me/identifiers/{id_type}   解绑（须保证至少剩一种可登录方式）
```

#### 验证码（找回/绑定/注册共用一套）

```
POST /v1/codes/send      { scene: "reset"|"bind"|"register", channel: "mail"|"sms", target }
POST /v1/codes/verify    { scene, channel, target, code }
```

  频控：同 target 60 秒一发、每日上限；同 ip 每小时上限；scene 绑定用途，
  注册码不能拿来重置密码。验证码只存哈希、5 分钟过期、验错 5 次作废。

#### 密码重置

```
POST /v1/password/reset   { target, code, new_password }   // 走验证码流程
```

#### MFA

```
POST /v1/users/me/mfa/setup     生成 TOTP secret + otpauth:// URI（含二维码内容）
POST /v1/users/me/mfa/enable    提交一次 TOTP 码确认绑定
POST /v1/users/me/mfa/disable   需密码或验证码确认
```

### 6.3 内省端点（产品服务端验 token）

产品拿到用户带来的 JWT 后，本地验签即可（JWKS 公钥），**无需每次调账号服务**；
只在需要实时状态（封禁即时生效、version 校验）时调内省：

```
POST /v1/introspect
请求:  { "token": "eyJ..." }
响应:  { "active": true, "open_id": "ga_x8f3a2...", "app_id": "game-a",
         "scope": "profile", "ver": 3, "status": 0, "realname": 1 }
```

  `active=false` 时给出 `reason`（expired/revoked/banned/version_stale）。

### 6.4 OIDC 标准端点（阶段 3，Web SSO 走这里）

```
GET  /.well-known/openid-configuration    发现文档
GET  /oauth2/jwks                          验签公钥（支持轮转，kid 标识）
GET  /oauth2/authorize                     授权页（统一登录 UI 挂这里）
POST /oauth2/token                         authorization_code(+PKCE) / refresh_token
GET  /oauth2/userinfo                      标准 claims，按 scope 返回
POST /oauth2/revoke                        撤销 token
```

  私有 API 的 `/v1/auth/login`（游戏/移动端直登）与 OIDC（Web 浏览器流）
  并存，背后是同一套账号存储和 token 体系。

### 6.5 管理端点（阶段 4，运营后台专用）

```
GET  /v1/admin/users?identifier=|uid=|mobile=     查账号（模糊查询须审计）
GET  /v1/admin/users/{uid}                        详情 + 全部 identifiers + user_app
POST /v1/admin/users/{uid}/ban                    全局封禁 { reason, duration }
POST /v1/admin/users/{uid}/unban
POST /v1/admin/apps/{app_id}/users/{open_id}/ban  单产品封禁（改 user_app.status）
CRUD /v1/admin/apps                               产品接入管理（secret 重置/回调地址）
GET  /v1/admin/audit?uid=|app_id=|op=             审计日志查询
```

  管理端点一律：独立权限校验（员工 SSO + 角色）、写操作全量落审计表、
  敏感字段（mobile/mail）默认脱敏返回，查看明文需二次授权并记审计。

### 6.6 限流与风控挂点

| 端点类别 | 限流维度 | 参考阈值 |
|---|---|---|
| login / codes/send | ip + identifier + device_id | 5 次/分钟后阶梯锁定 |
| register | ip + device_id | 10 次/小时 |
| 其余用户端点 | open_id | 60 次/分钟 |
| introspect / 产品服务签名 | app_id | 按接入协议约定配额 |

超限返回 `42901` + `Retry-After`。风控引擎（阶段 4）以中间件形式挂在
login/register/codes 三个高危端点上，对 API 形状无侵入。

---

## 7. 安全补课（当前库的欠账）

| 项 | 现状 | 目标 |
|---|---|---|
| 密码哈希 | 原样存储，外层决定 | 服务端统一 argon2id（pass 列宽 98 已够），登录取出后 verify，废弃 `WHERE pass=?` 匹配（哈希化后不成立，且有时序侧信道） |
| 暴力破解 | 无防护 | 登录失败计数 + 阶梯锁定、按 IP/设备限流、验证码钩子 |
| 异地登录 | 只记录 ip | 异地检测 + 通知（ip 字段是基础） |
| 找回/改密 | passwd() 裸改 | 邮件/短信验证码子系统（带发送频控）；改密后踢掉全部 refresh_token |
| MFA | 无 | TOTP 可选能力（内部产品和付费游戏大概率会要） |
| 审计 | 仅 logger | 敏感操作（改密/封禁/绑定第三方/授权）落独立审计表，只追加 |
| 实名/防沉迷 | 无 | 游戏产品国内绕不开：预留实名认证状态字段、未成年人宵禁/时长查询接口（数据可对接第三方，账号服务只存状态） |
| PII | 明文 | 敏感字段加密存储、日志脱敏 |

---

## 8. 工程形态

- **连接池**：现 `AccountMySQL` 单连接 + RLock 全局串行化，服务化后是第一个
  瓶颈，换连接池（每请求一连接）
- **无状态服务**：水平扩容，LB 后多实例；会话/token 状态全在 Redis
- **登录路径优化**：现 `login()` 查两次（验证 + 统计后重查），服务化时合并；
  登录统计异步化（消息队列），认证路径上不做非必要写
- **管理端**：运营后台 API + 界面（查账号、封禁/解封、解绑第三方、审计查询）
  ——这是"服务"而非"库"才能提供的东西

服务实现语言建议：团队 Python 为主则 **FastAPI + 现有存储层**起步，改造成本
最低；账号服务的 QPS 瓶颈通常在数据库和风控逻辑，不在语言。真出现性能瓶颈
再考虑 Go。

---

## 9. 分阶段路线

| 阶段 | 内容 | 产出 |
|---|---|---|
| **1. 模型收敛** | 砍业务字段、UTC、status 扩展、设计 account/apps/identifiers/user_app 四表；`accountz.py` 退化为账号服务内部存储层（只留 MySQL 后端） | 新版 schema + 存储层 |
| **2. 服务化** | FastAPI 包一层，先做私有 API（register/login/query/passwd/ban + app_id/secret 鉴权），JWT token，Redis 会话；接入第一个产品 | 账号服务 MVP |
| **3. 标准化** | OIDC（authorize/token/userinfo/JWKS）、SSO 免登、单点登出、scope 授权 | 各产品用标准客户端库接入 |
| **4. 生态完善** | 第三方登录、MFA、风控限流、实名/防沉迷钩子、审计、运营后台 | 全功能统一账号平台 |

阶段 2 结束即可给第一个产品供服务，阶段 3/4 边接入边补。

---

## 10. 现有代码的资产盘点

可直接带进新架构的部分：

- **`AccountBase` 字段校验体系**：类型/长度/值域三端统一校验的思路，服务化后
  收敛成单端校验，逻辑照用
- **int64 溢出防护、金额整数分设计**：输出给独立的钱包/支付服务
- **`populate_fake_data()`**：压测和联调造数据，分布设计贴近真实，非常有用
- **三后端一致性经验**：哪些坑（隐式类型转换、大小写敏感 collation、
  CHECK 约束差异）在新 schema 设计时直接规避

应淘汰的部分：

- mongo 后端、sqlite 生产用途（仅留开发测试）
- `payment()/deposit()` 全套（移交钱包服务）
- 单连接 + RLock 的并发模型
- `WHERE pass=?` 明文比对式登录
