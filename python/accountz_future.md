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

从现有 account 表剥离全部业务字段：

- **删除**：`level` `exp` `icon` `sign` `intro` `photo` `credit` `gold`
  `CreditConsumed` `GoldConsumed`，以及整个 `payment()/deposit()` 体系
  （余额与消费流水属于各业务方或独立的钱包/支付服务）
- **保留**：`uid` `pass` `name` `gender` `birthday` `mail` `mobile`
  `status` `src` `ip` `RegDate` `LastLoginDate` `LoginTimes` `misc`
- **废弃**：`urs` 列（登录名迁到 `identifiers` 表）、`cid` 列
  （外部 uid 的语义被 per-app open_id 取代）

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

## 6. 安全补课（当前库的欠账）

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

## 7. 工程形态

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

## 8. 分阶段路线

| 阶段 | 内容 | 产出 |
|---|---|---|
| **1. 模型收敛** | 砍业务字段、UTC、status 扩展、设计 account/apps/identifiers/user_app 四表；`accountz.py` 退化为账号服务内部存储层（只留 MySQL 后端） | 新版 schema + 存储层 |
| **2. 服务化** | FastAPI 包一层，先做私有 API（register/login/query/passwd/ban + app_id/secret 鉴权），JWT token，Redis 会话；接入第一个产品 | 账号服务 MVP |
| **3. 标准化** | OIDC（authorize/token/userinfo/JWKS）、SSO 免登、单点登出、scope 授权 | 各产品用标准客户端库接入 |
| **4. 生态完善** | 第三方登录、MFA、风控限流、实名/防沉迷钩子、审计、运营后台 | 全功能统一账号平台 |

阶段 2 结束即可给第一个产品供服务，阶段 3/4 边接入边补。

---

## 9. 现有代码的资产盘点

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
