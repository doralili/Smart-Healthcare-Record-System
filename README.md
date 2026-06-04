[README.md](https://github.com/user-attachments/files/28345175/README.md)
# Smart Healthcare Record System

智慧医疗病历安全系统，面向《Computer and Data Security》group project。项目目标不是实现完整医院信息系统，而是通过一个可运行 Demo 展示电子病历场景中的数据安全机制：默认临床授权、患者可撤回授权、医生按权限访问、病历加密存储、敏感字段脱敏、访问行为审计，以及审计日志防篡改验证。

## 项目定位

本系统围绕“医疗记录不能被任意医生或管理员随意查看”这一安全问题展开。医生与患者存在医患关系时，系统默认授予医生访问必要病历信息的权限，以贴近日常医疗系统和小程序授权体验；患者仍然可以查看当前医生访问权限，并随时撤销授权。医生如果需要访问默认范围之外的内容，则需要提交额外授权申请。

项目重点对应课程中的以下安全主题：

- Confidentiality：病历加密存储、授权访问、字段脱敏
- Integrity：审计日志哈希链、防篡改验证
- Authentication：用户登录、JWT 身份认证
- Access Control：角色权限控制、默认授权、额外授权、撤销授权
- Accountability：所有关键访问行为写入审计日志

## 核心功能

### 账号与角色

- 用户名密码登录
- 密码使用 `bcrypt` 哈希存储
- 登录后签发 `JWT`
- 根据角色进入不同页面
- 角色包括：患者、医生、管理员、审计员

### 医生端

- 首页展示“我的病人列表”，按状态分组（Full Access、Default Access、Pending Approval、Rejected、Revoked）
- 默认授权病人可直接查看默认范围内的必要病历信息
- 医生可搜索患者并提交授权申请（支持 Default Access 和 Full Access）
- 超出默认范围的内容需要提交额外授权申请
- 默认授权和患者批准的授权默认有效期为 14 天，过期后医生需要重新获得授权
- 被拒绝的申请可重新提交
- 患者撤销授权后，医生再次访问会被拒绝

### 患者端

- 查看自己的加密病历并自动解密展示
- 查看哪些医生拥有访问权限
- 查看医生待审批的授权申请
- 审批或拒绝医生的授权申请
- 随时撤销医生的访问权限
- 查看自己的病历诊断、检查结果、用药记录等

### 病历安全

- 使用 Synthea 生成合成医疗数据，避免真实隐私风险
- 病历正文以结构化 JSON 表示
- 入库前使用 AES-GCM 加密
- 数据库中不保存明文诊断、化验、用药、病程记录等敏感内容
- 后端只在权限校验通过后解密
- 返回前按授权范围做字段脱敏

### 审计与防篡改

- 记录登录、默认授权创建、额外授权申请、授权审批、撤销授权、查看病历、访问拒绝等行为
- 每条审计日志保存上一条日志哈希和当前日志哈希
- 审计员可以运行完整性验证
- 手动篡改旧日志后，系统应能检测出日志链异常

## 技术栈

| 层次 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | FastAPI |
| 数据库 | openGauss |
| ORM | SQLAlchemy 2.x |
| 数据库驱动 | `psycopg2` / PostgreSQL 兼容驱动 |
| 登录认证 | JWT |
| 密码存储 | bcrypt |
| 病历加密 | Python `cryptography` 库的 AES-256-GCM |
| 审计完整性 | SHA-256 哈希链 |
| 数据来源 | Synthea 合成医疗数据 |
| 接口文档 | FastAPI 自动生成 Swagger / OpenAPI |

## 系统架构

```mermaid
flowchart LR
    U["用户浏览器<br/>患者 / 医生 / 管理员 / 审计员"] --> F["前端 Web 应用<br/>Vue 3 + Vite + Element Plus"]
    F --> B["后端 API 服务<br/>FastAPI"]
    B --> A["认证与权限模块<br/>JWT + RBAC"]
    B --> C["授权模块<br/>默认授权 + 额外授权 + 撤销"]
    B --> E["加密与脱敏模块<br/>AES-GCM + Masking"]
    B --> L["审计日志模块<br/>SHA-256 Hash Chain"]
    B --> D["openGauss 数据库"]
    S["Synthea 合成医疗数据"] --> I["数据导入脚本"]
    I --> B
```

## 核心访问流程

1. 用户登录后，后端根据 JWT 识别身份和角色。
2. 医生进入首页，看到“我的病人列表”。
3. 对默认授权状态的病人，医生可以查看默认范围内的必要病历信息。
4. 后端仍会校验医生角色、授权状态、授权范围和授权有效期。
5. 如果医生需要访问默认范围之外的病历内容，需要提交额外授权申请。
6. 患者可以查看医生访问权限，并随时撤销默认授权或额外授权。
7. 校验通过后，后端解密病历，按授权范围脱敏，再返回给前端。
8. 每一次允许、拒绝、授权创建或撤销都会写入审计日志。
9. 审计员可以验证日志哈希链，发现日志是否被篡改。

## 主要数据表

| 表名 | 用途 |
|---|---|
| `users` | 登录账号、密码哈希、角色、状态 |
| `patients` | 患者基本信息，与用户账号关联 |
| `medical_records` | 加密后的病历数据、nonce、来源、记录类型 |
| `doctors` | 医生信息、科室、执照号、审核状态|
| `consents` | 默认临床授权、额外访问申请与患者撤销记录|
|`access_logs`|医生查看/拒绝查看病历的访问日志|
| `audit_logs` | 带 SHA-256 哈希链的安全审计日志 |

## 最小演示目标

- 数据库中病历是密文，不能直接看到明文医疗内容
- 医生首页展示“我的病人列表”
- 医生可查看默认授权范围内的病历内容
- 医生申请查看默认范围之外的内容时，需要患者额外审批
- 患者撤销授权后，医生再次访问对应病历范围会被拒绝
- 每一次访问和拒绝访问都会写入审计日志
- 审计员可以验证日志哈希链完整性
- 手动篡改旧日志后，系统能检测出异常

## 目前已完成的工作

### 后端

- 建立 FastAPI 后端项目结构。
- 实现登录接口、患者注册接口、当前用户识别、角色依赖 `require_roles()`。
- 患者可以自助注册；医生、管理员、审计员账号不开放自助注册，应由管理员或种子数据统一发放。
- 密码使用 `bcrypt` 哈希，登录成功后签发 JWT。
- 后端从 `backend/.env` 读取数据库、JWT、病历加密密钥等配置；数据库连接、JWT 密钥和病历加密密钥不再在源码中提供默认值。
- `.env` 读取使用 `utf-8-sig`，兼容 Windows 下带 BOM 的配置文件。
- 密码校验直接使用 `bcrypt` 包，避免当前环境中 `passlib + bcrypt` 版本兼容导致登录 500。
- 删除角色校验中的调试输出，避免在控制台泄露用户名、角色等认证细节。
- 增加 `MEDICAL_RECORD_KEY` 配置，用于 AES-GCM 病历加密。
- 增加北京时间工具 `backend/app/core/timezone.py`。
- 增加 `patients`、`medical_records`、`consents`、`access_logs`、`audit_logs` SQLAlchemy 模型。
- 增加患者本人病历接口：
  - `GET /api/patient/me/records`
  - `GET /api/patient/me/records/{record_id}`
- 增加患者授权管理接口：
  - `GET /api/patient/me/records/pending-consents`（查看待审批申请）
  - `POST /api/patient/me/records/consents/{id}/approve`（批准申请）
  - `POST /api/patient/me/records/consents/{id}/reject`（拒绝申请）
  - `GET /api/patient/me/records/my-doctors`（查看已授权医生）
  - `POST /api/patient/me/records/consents/{id}/revoke`（撤销授权）
- 增加医生端接口：
  - `GET /api/doctor/my-patients`（我的病人列表，按状态分组）
  - `POST /api/doctor/access-requests`（提交授权申请）
  - `GET /api/doctor/patients/{patient_id}/records`（查看脱敏病历）
  - `GET /api/doctor/search-patients`（搜索患者，带状态标识）
- 当前版本中，医生申请 `EXTRA` 权限不会覆盖已有 `DEFAULT ACTIVE` 授权；医生患者列表不返回电话和地址，默认授权范围下电话和地址均会脱敏。
- 增加审计员接口：
  - `GET /api/auditor/summary`（审计日志统计）
  - `GET /api/auditor/audit-logs`（查看最近审计日志）
  - `GET /api/auditor/verify-hash-chain`（验证审计日志哈希链）
- 患者接口会校验当前用户必须是 `PATIENT`，并且只能访问绑定到自己账号的病历。
- 增加 `backend/app/services/crypto_service.py`，用于加密和解密结构化病历 JSON。
- 增加 `backend/scripts/import_synthea_records.py`：
  - 读取 `synthea/output/fhir/*.json`
  - 解析 `Patient`、`Encounter`、`Condition`、`Observation`、`MedicationRequest`、`Procedure`
  - 跳过已死亡患者
  - 跳过已存在患者
  - 将导入患者绑定到患者演示账号
  - 将结构化病历加密写入 `medical_records`


### 数据库

- `users.created_at`、`users.last_login_at` 改为 `TIMESTAMPTZ`。
- 新增 `patients` 表，保存合成患者基础信息。
- 新增 `medical_records` 表，保存加密病历、nonce、数据来源和记录类型。
- 新增 `consents` 表，保存授权记录（status: ACTIVE/PENDING/REJECTED/REVOKED，scope: DEFAULT/EXTRA）。
- 新增 `access_logs` 表，保存审计日志。
- 新增 `audit_logs` 表，保存登录、授权、病历访问等关键事件及 SHA-256 哈希链；当前版本额外记录 IP 地址和 User-Agent。
- 保留演示账号种子 SQL：`database/seed_users.sql`。
- 新增一键 Demo 数据库脚本：`database/setup_demo_database.ps1`。
- 当前本地新版开发库使用独立容器 `healthcare-opengauss-dev`，映射到本机 `5433`，数据库名为 `health_security`。
- 当前新版开发库保留 10 个患者和 10 条加密病历，`patient1` 到 `patient10` 分别绑定到这 10 个患者账号；无账号患者及其病历已清理。



### 前端

- 实现登录页、JWT 保存、角色路由跳转和退出登录。
- 登录页新增 `Login / Patient Sign Up` 切换；注册入口只创建 `PATIENT` 用户。
- 登录页和管理员重置密码弹窗不再预填默认密码。
- 登录页支持回车提交，避免重复提交。
- Dashboard 顶部显示用户名和角色标签。
- 前端 API 地址统一使用 `http://127.0.0.1:8000`。
- 新增患者病历 API 封装 `frontend/src/api/patientRecords.ts`。
- 新增患者授权管理 API 封装 `frontend/src/api/patientAuth.ts`。
- 新增医生端 API 封装 `frontend/src/api/doctor.ts`。
- 患者端 Dashboard 已从占位页升级为可用病历页面：
  - 加载患者本人加密病历并展示解密后的内容
  - 展示患者基本信息
  - 展示 visits、diagnoses、lab/vital results、medications、procedures 统计
  - 诊断列表支持按日期搜索
  - 诊断详情抽屉展示相关就诊、用药、检查和操作
  - 未能关联到诊断的临床记录按年/月/日分组展示
  - **新增"Doctor Authorization"Tab**：
    - 查看待审批的医生授权申请
    - 批准/拒绝医生的申请
    - 查看已授权的医生列表
    - 撤销医生访问权限
- 医生端 Dashboard 已从占位页升级为完整功能页面：
  - 我的病人列表按 5 个状态分组（Full Access、Default Access、Pending Approval、Rejected、Revoked）
  - 查看患者的脱敏病历
  - 申请 Full Access 权限
  - **新增搜索患者页面**：
    - 按姓名搜索患者
    - 根据授权状态显示不同的操作按钮
    - 支持申请 Default Access 和 Full Access
    - 被拒绝后可重新申请
- 审计员 Dashboard 已从占位页升级为审计页面：
  - 查看审计日志总数、拒绝事件数和最新事件时间
  - 查看各类审计动作统计
  - 查看最近审计日志及哈希摘要
  - 查看审计日志中的 IP 和 User-Agent
  - 一键验证 SHA-256 哈希链完整性
- 管理员 Dashboard 已从占位页升级为管理页面：
  - 查看用户、医生、患者、禁用账号、病历、授权和审计日志数量
  - 创建医生账号；当前版本不允许通过页面创建管理员或审计员高权限账号
  - 启用/禁用账号，重置密码
  - 审核医生账号，从固定科室选项中维护科室、执业编号和备注
  - 将患者分配给已审核医生，并自动生成 DEFAULT_CLINICAL 默认授权
  - 展示管理员只能查看统计，不能查看解密病历正文的安全边界

## 当前实现进度

| 模块 | 状态 | 说明 |
|---|---|---|
| 项目初始化 | 已完成 | FastAPI 后端、Vue 3 前端、基础目录结构和开发启动脚本已建立 |
| 登录、患者注册与角色权限 | 已完成 | bcrypt 密码哈希、JWT 登录、患者自助注册、当前用户识别和基础 RBAC 已实现；医生等高权限账号统一发放 |
| openGauss 数据库连接 | 已完成 | 使用 PostgreSQL 兼容方式连接 openGauss |
| 数据库一键准备脚本 | 已完成初版 | 可创建新容器，并复制现有数据库或初始化干净数据库 |
| Synthea 数据导入 | 已完成初版 | 可导入 FHIR JSON，生成患者信息和结构化病历 |
| 病历加密存储 | 已完成初版 | AES-GCM 加密病历 JSON，数据库中不保存明文病历正文 |
| 患者本人查看病历 | 已完成初版 | 患者演示账号登录后可查看绑定到自己的病历 |
| 医生“我的病人列表” | 已完成 | 按 Full Access、Default Access、Pending Approval、Rejected、Revoked 五组显示 |
| 医生搜索患者| 已完成 | 支持按姓名模糊查询搜索，根据授权状态显示不同操作按钮 |
| 默认授权与撤销 | 已完成 | 患者可查看已授权医生并撤销；默认授权有效期为 14 天 |
| 额外授权申请 |  已完成  | 医生提交 → 患者审批 → 授权生效的完整流程；批准后有效期为 14 天 |
| 字段脱敏策略 | 已完成  | 查看待审批申请、批准/拒绝、查看已授权医生、撤销授权 |
| 审计日志 | 已完成初版 | `access_logs` 记录医生访问，`audit_logs` 记录登录、授权、病历访问、拒绝事件、IP 和 User-Agent |
| 哈希链完整性验证 | 已完成初版 | `audit_logs` 使用 SHA-256 前后哈希链，审计员可验证完整性 |
| 管理员页面 | 已完成初版 | 可管理账号、审核医生、分配默认医患授权，并查看只读系统安全状态 |
| 审计员页面 | 已完成初版 | 可查看审计统计、日志列表并验证哈希链 |

其中 `access_logs` 表包含的字段有：id，doctor_id，patient_id，consent_id，action，record_scope。

其中 `audit_logs` 表包含的关键字段有：actor_user_id，actor_role，actor_username，action，doctor_id，patient_id，consent_id，record_scope，outcome，detail，ip_address，user_agent，previous_hash，current_hash。


## 项目结构

```text
Smart-Healthcare-Record-System/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # API 路由
│   │   │   ├── auth.py         # 登录认证
│   │   │   ├── doctor.py       # 医生端接口
│   │   │   ├── patient_records.py  # 患者病历和授权接口
│   │   │   └── ...
│   │   ├── core/               # 配置、认证、安全工具
│   │   ├── db/                 # SQLAlchemy session
│   │   ├── models/             # 数据库模型
│   │   ├── schemas/            # 请求/响应结构
│   │   └── services/           # 加密等业务服务
│   ├── scripts/                # Synthea 导入脚本
│   ├── requirements.txt
│   └── run_dev.ps1
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/                # 前端 API 封装
│   │   │   ├── auth.ts         # 认证 API
│   │   │   ├── doctor.ts       # 医生端 API
│   │   │   ├── patientRecords.ts   # 患者病历 API
│   │   │   └── patientAuth.ts      # 患者授权 API
│   │   ├── layouts/            # 页面布局
│   │   ├── router/             # 路由和角色跳转
│   │   ├── stores/             # Pinia 状态
│   │   └── views/              # 登录页和各角色页面
│   │       ├── Login.vue
│   │       ├── PatientDashboard.vue   # 患者端（病历+授权管理）
│   │       ├── DoctorDashboard.vue    # 医生端（病人列表+搜索）
│   │       ├── AdminDashboard.vue
│   │       └── AuditorDashboard.vue
│   └── run_dev.ps1
├── database/
│   ├── schema.sql              # 建表 SQL
│   ├── seed_users.sql          # 演示账号 SQL
│   ├── seed_demo_core.sql      # doctor1 和默认授权演示数据
│   └── setup_demo_database.ps1 # 一键创建数据库、建表并导入演示数据
├── docs/                       # 项目设计、计划、接口边界文档
├── synthea/                    # Synthea 生成器与输出数据
└── README.md
```

## 运行方式

以下步骤默认在 Windows PowerShell 中执行。先进入项目根目录：

```powershell
cd "C:\Users\27726\Documents\lxt\Learning\Sophomore\Second term\Computer security\group project"
```

如果你的项目路径不同，请替换成自己的路径。

### 0. 检查基础工具

检查 Docker：

```powershell
docker --version
docker ps
```

如果 `docker ps` 报错，先启动 Docker Desktop。

检查 Python：

```powershell
python --version
```

建议使用 Python 3.10 或更新版本。

检查 Node.js 和 npm：

```powershell
node --version
npm --version
```

建议使用 Node.js 20 或更新版本。

检查 Java：

```powershell
java -version
```

Synthea 需要 Java JDK 17 或更新版本。如果没有 Java，或版本低于 17，可以使用 winget 安装：

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
```

安装完成后，关闭当前 PowerShell，重新打开，再检查：

```powershell
java -version
```

如果 `winget` 不可用，可以先搜索可安装的 JDK：

```powershell
winget search JDK
```

然后安装一个 JDK 17 或更新版本。

### 1. 允许本地 PowerShell 脚本运行

如果运行 `.ps1` 脚本时报执行策略错误，执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

如果系统询问是否确认，输入：

```text
Y
```

### 2. 配置后端 `.env`

复制示例配置：

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

一键数据库脚本会从 `backend/.env` 读取 `JWT_SECRET` 和 `MEDICAL_RECORD_KEY`。如果你要重新导入 Synthea 病历，必须先配置 `MEDICAL_RECORD_KEY`，并且后续运行后端时继续使用同一把密钥。

生成新的病历加密密钥：

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
[Convert]::ToBase64String($bytes)
```

复制输出的 base64 字符串，打开配置文件：

```powershell
notepad .\backend\.env
```

`.env.example` 是通用模板。使用一键脚本默认参数时，可以把 `.env` 改成：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@127.0.0.1:5433/health_security
JWT_SECRET=replace_with_your_own_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MEDICAL_RECORD_KEY=把base64密钥粘贴到这里
TZ=Asia/Shanghai
```

注意：数据库密码里的 `@` 在 URL 中要写成 `%40`，所以 `Healthcare@123` 在 `DATABASE_URL` 里写成 `Healthcare%40123`。

注意：上方 `DATABASE_URL`、`JWT_SECRET` 一直到 `TZ` 都要按 `.env.example` 中的变量名配置。不要把后端数据库用户改回 `omm`，否则可能出现：

```text
Forbid remote connection with initial user
```

出现该错误时，把 `DATABASE_URL` 改回 `healthcare` 用户，并确认已经执行过“创建后端数据库用户”的 SQL。

注意：`MEDICAL_RECORD_KEY` 必须是 base64 编码后的 32 字节密钥。如果数据库里已经有加密病历，换密钥后旧病历将无法解密。

如果你用了其他端口，例如 `15432`，则改成：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@127.0.0.1:15432/health_security
```

### 3. 一键准备 openGauss 数据库和演示数据

项目提供一键 Demo 数据库脚本：

```text
database/setup_demo_database.ps1
```

这个脚本可以重复执行，不会重复建表，也不会重复插入同一批测试数据。它会完成：

1. 如果目标容器不存在，则新建 openGauss 容器；如果已存在，则直接启动或复用。
2. 如果 `health_security` 数据库不存在，则创建数据库。
3. 执行 `database/schema.sql`，创建全部表和索引。
4. 执行 `database/seed_users.sql`，插入 `patient1` 到 `patient10`、`doctor1`、`admin`、`auditor`。
5. 创建或授权后端数据库用户，默认是 `healthcare / Healthcare@123`。
6. 调用 `backend/scripts/import_synthea_records.py`，从 `synthea/output/fhir/*.json` 导入 10 个合成患者，并加密写入 `medical_records`。
7. 执行 `database/seed_demo_core.sql`，插入或更新 `doctor1` 的医生资料，并给 `doctor1` 和 `patient1` 建立一条 `DEFAULT` 授权。
8. 输出各表行数，方便检查初始化结果。

运行代码：（推荐使用独立容器和默认端口）

```powershell
.\database\setup_demo_database.ps1 -TargetContainer healthcare-opengauss-dev -HostPort 5432
```

脚本会自动检测容器、数据库、表和演示数据是否已经存在。重复运行同一条命令不会重复建表，也不会重复插入同一批测试数据。

如果本机确实需要使用其他容器名、端口或数据库用户，可以通过参数覆盖：

```powershell
.\database\setup_demo_database.ps1 -TargetContainer 自己的容器名 -HostPort 自己的端口 -AppUser 自己的数据库用户 -AppPassword "自己的数据库密码"
```

重要说明：

- `omm` 是 openGauss 容器内部的管理用户，适合在容器内执行 `gsql`，但后端 `.env` 不要使用 `omm` 远程连接。
- 前端不直接连接数据库，前端只调用后端 API；后端使用 `.env` 中的普通应用用户连接数据库。
- `patients` 和 `medical_records` 只绑定到 `patient1` 到 `patient10` 这 10 个演示账号；后续新注册患者不会复用这 10 条病历。
- `access_logs` 和 `audit_logs` 默认可以为空，它们会在登录、授权、查看病历、拒绝访问等真实操作后产生。

### 4. 安装后端依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
```

### 5. 安装前端依赖

```powershell
cd frontend
npm.cmd install
cd ..
```

### 6. 生成或使用 Synthea 合成数据

仓库中已经包含少量示例数据：

```text
synthea/output/fhir/
synthea/output/csv/
```

如果只是想快速跑通 Demo，可以跳过本步骤，直接使用仓库中已有的示例 FHIR 数据。

如果需要重新生成数据，先确认 Java：

```powershell
java -version
```

然后执行：

```powershell
cd synthea
java -jar .\synthea-with-dependencies.jar -p 10 --exporter.fhir.export=true --exporter.csv.export=true
cd ..
```

参数说明：

```text
-p 10                         生成 10 个合成患者
--exporter.fhir.export=true   输出 FHIR JSON
--exporter.csv.export=true    输出 CSV
```

生成结果位置：

```text
synthea/output/fhir/
synthea/output/csv/
```

### 7. 检查数据库演示数据

正常情况下，`setup_demo_database.ps1` 已经导入合成病历，不需要手动执行导入脚本。脚本完成后的基础数据应为：

```text
users: 13
patients: 10
medical_records: 10
patients_without_account: 0
records_without_patient: 0
```

如果你修改或重新生成了 `synthea/output/fhir/*.json`，可以重新运行一键脚本导入。导入逻辑是幂等的：已经存在的患者和病历不会重复插入。

检查数据库中是否有患者和病历：

```powershell
docker exec -it healthcare-opengauss-dev bash
```

容器中执行：

```bash
su - omm
gsql -d health_security
```

查询：

```sql
SELECT id, user_id, full_name, synthea_patient_id FROM patients;
SELECT id, patient_id, source, record_type, created_at FROM medical_records;
```

验证病历是密文：

```sql
SELECT id, left(encrypted_data, 80) AS encrypted_preview, nonce FROM medical_records;
```

退出：

```sql
\q
```

```bash
exit
exit
```

### 8. 启动后端

新开一个 PowerShell 窗口：

```powershell
cd "C:\Users\27726\Documents\lxt\Learning\Sophomore\Second term\Computer security\group project"
cd backend
C:\Users\27726\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/health
```

Swagger / OpenAPI 文档：

```text
http://127.0.0.1:8000/docs
```

### 9. 启动前端

再新开一个 PowerShell 窗口：

```powershell
cd "C:\Users\27726\Documents\lxt\Learning\Sophomore\Second term\Computer security\group project"
cd frontend
npm.cmd run dev -- --host 127.0.0.1
```

前端默认地址：

```text
http://127.0.0.1:5173
```

前端命令会在当前 PowerShell 窗口运行 Vite。终端输出端口后，在浏览器打开对应地址即可。

### 10. 登录演示

打开：

```text
http://localhost:5173
```

患者账号示例：

```text
用户名：patient1
密码：password123
```

`patient1` 到 `patient10` 都是患者演示账号，密码相同。登录后进入 `/patient`，可以查看患者基础信息、诊断列表、相关就诊记录、检查和生命体征、用药、操作记录，以及未关联到诊断的临床记录分组。

登录页也提供 `Patient Sign Up`，用于创建新的患者账号。注册接口不会接受角色参数，新账号固定为：

```text
role=PATIENT
status=ACTIVE
```

医生、管理员、审计员账号不允许自助注册，应通过管理员功能或种子 SQL 统一发放。

## 演示账号

所有演示账号的密码均为：

```text
password123
```

| 用户名 | 角色 | 登录后页面 | 当前可演示内容 |
|---|---|---|---|
| `patient1` - `patient10` | `PATIENT` | `/patient` | 查看绑定到自己的加密病历 |
| `doctor1` | `DOCTOR` | `/doctor` | 审核通过后可查看病人列表、搜索患者和申请授权 |
| `admin` | `ADMIN` | `/admin` | 账号管理、医生审核、医患分配和系统安全状态 |
| `auditor` | `AUDITOR` | `/auditor` | 查看审计统计、审计日志和哈希链验证结果 |

## 当前可演示流程

1. 配置 `backend/.env`，填写数据库连接、`JWT_SECRET` 和 `MEDICAL_RECORD_KEY`。
2. 执行 `database/setup_demo_database.ps1` 准备 openGauss 容器、数据库、表结构和演示数据。
3. 安装后端依赖和前端依赖。
4. 如有需要，使用 Synthea 重新生成合成数据，再重新执行一键数据库脚本导入。
5. 启动后端和前端。
6. 使用 `patient1` 到 `patient10` 中任意已绑定病历的患者账号登录，密码为 `password123`。
7. 进入患者 Dashboard，查看患者基础信息、诊断列表、相关就诊、检查、用药、操作记录。
8. 查询 `medical_records.encrypted_data`，验证病历正文以密文保存。

### 管理员端

1. 使用 admin 登录，进入 Admin Dashboard。
2. 在 Doctor Review 中从固定选项选择医生科室，并维护执业编号和备注。
3. 将医生 Review 设置为 Approved，医生通过审核后才能访问医生端业务接口。
4. 在 Patient Assignment 中选择已审核医生和患者，生成有效期 14 天的 DEFAULT_CLINICAL 默认授权。
5. 查看系统状态和安全边界提示，确认管理员只能看统计，不能查看解密病历正文。

### 医生端

1. 确认 doctor1 已由管理员审核通过。
2. 使用 doctor1 登录，进入医生 Dashboard，查看 “我的病人列表”（5 个分组）。
3. 点击 “搜索患者”，输入患者名称搜索，根据患者授权状态显示智能操作按钮。
4. 对未授权患者，提交 DEFAULT/EXTRA 类型授权申请（填写申请理由）。
5. 申请提交后，患者端会显示待审批申请，医生端患者移至 Pending Approval 分组。
6. 患者批准申请后，医生端患者移至对应分组（Default Access/Full Access）。
7. 点击 “查看病历”，查看按授权范围脱敏后的患者病历内容。
8. 患者撤销授权后，医生端患者移至 Revoked 分组，再次查看病历会被拒绝。
9. 被拒绝的申请可重新提交，已有 Full Access 的患者不显示申请按钮，已有 Default Access 的患者只显示 Apply Full Access 按钮。

### 患者端
1. 使用 patient1-10 登录，进入患者 Dashboard，查看本人病历、统计数据、诊断列表。
2. 切换到 Doctor Authorization Tab，查看待审批授权申请。
3. 对申请进行批准 / 拒绝操作（可填写审批备注）。
4. 查看已授权医生列表，对任意医生执行撤销授权操作。
5. 撤销授权后，对应医生将无法再查看该患者病历。

### 审计员端
1. 使用 auditor 登录，进入 Auditor Dashboard。
2. 查看审计日志总数、拒绝事件数、最新事件时间和动作统计。
3. 查看最近审计日志列表，确认登录、授权申请、审批/拒绝/撤销、病历访问和拒绝访问均被记录。
4. 点击 Verify Hash Chain，验证 `audit_logs` 中的 SHA-256 哈希链是否完整。
5. 如果手动篡改旧日志的关键字段，验证结果会提示断裂位置。

如果需要在数据库里手动查看或篡改审计日志做演示，进入 `health_security` 后直接操作 `audit_logs` 表。

## 后续待办

- 准备最终演示脚本和报告截图。


## 参考文档

- [项目设计文档](docs/PROJECT_DESIGN.md)
- [中文计划书](docs/GROUP_PROJECT_PLAN_CN.md)
- [接口边界文档](docs/API_BOUNDARY.md)
