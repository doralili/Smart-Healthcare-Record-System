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
|`access_logs`|安全审计日志，已创建表结构|
| `audit_logs` | 安全审计日志和哈希链字段，待实现 |

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
- 后端从 `backend/.env` 读取数据库、JWT、病历加密密钥等配置。
- 增加 `MEDICAL_RECORD_KEY` 配置，用于 AES-GCM 病历加密。
- 增加北京时间工具 `backend/app/core/timezone.py`。
- 增加 `patients`、`medical_records`、`consents`、`access_logs` SQLAlchemy 模型。
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
- 保留演示账号种子 SQL：`database/seed_users.sql`。
- 新增一键数据库脚本：`database/setup_opengauss_copy.ps1`。
- 当前本地新版开发库使用独立容器 `healthcare-opengauss-dev`，映射到本机 `5433`，数据库名为 `health_security`。
- 当前新版开发库已导入 100 个患者和 100 条加密病历，`patient1` 到 `patient10` 已绑定到前 10 个患者账号。



### 前端

- 实现登录页、JWT 保存、角色路由跳转和退出登录。
- 登录页新增 `Login / Patient Sign Up` 切换；注册入口只创建 `PATIENT` 用户。
- 登录页支持回车提交，避免重复提交。
- Dashboard 顶部显示用户名和角色标签。
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
| 默认授权与撤销 | 已完成 | 患者可查看已授权医生并撤销  |
| 额外授权申请 |  已完成  | 医生提交 → 患者审批 → 授权生效的完整流程  |
| 字段脱敏策略 | 已完成  | 查看待审批申请、批准/拒绝、查看已授权医生、撤销授权 |
| 审计日志 | 已创建表结构 |  `access_logs` 表已创建，待成员 D 完善哈希链验证 |
| 哈希链完整性验证 | 未完成 | 后续实现 |
| 管理员/审计员页面 | 占位完成 | 登录和跳转可用，业务功能待补充 |

其中已建立的access_logs表包含的字段有：id，doctor_id，patient_id ，consent_id，action，record_scope


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
│   └── setup_opengauss_copy.ps1 # 一键创建/复制数据库脚本
├── docs/                       # 项目设计、计划、接口边界文档
├── synthea/                    # Synthea 生成器与输出数据
└── README.md
```

## 运行方式

以下步骤默认在 Windows PowerShell 中执行。先进入项目根目录：

```powershell
cd D:\VScode-files\Smart-Healthcare-Record-System
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

### 2. 一键准备 openGauss 数据库容器

项目提供脚本：

```text
database/setup_opengauss_copy.ps1
```

脚本会创建或启动目标 openGauss 容器，等待数据库就绪，创建 `health_security` 数据库，并从 SQL dump 文件恢复表结构和表数据。

当前本地开发环境建议使用独立容器：

```text
healthcare-opengauss-dev  ->  localhost:5433/health_security
```

旧容器 `my_opengauss` 中还保留其他项目的 `music` 数据库，不要把它当作本项目新版主库，也不要删除该容器。

#### 使用数据库 dump 文件恢复

把dump文件放到：

```text
database/health_security.copy.sql
```

然后在项目根目录执行：

```powershell
.\database\setup_opengauss_copy.ps1 -DumpFilePath .\database\health_security.copy.sql
```

这会创建新的 openGauss 容器，并把 dump 文件里的表结构和数据恢复进去，包括 `users`、`patients`、`medical_records` 等表。

导入consent,access_log表：
1.从宿主机复制到容器
```
docker cp D:/Smart-Healthcare-Record-System/database/consents_schema.sql healthcare-opengauss-dev:/tmp/consents_schema.sql
docker cp D:/Smart-Healthcare-Record-System/database/access_logs_schema.sql healthcare-opengauss-dev:/tmp/access_logs_schema.sql
```
2.执行导入
```
docker exec -it healthcare-opengauss-dev bash
su - omm
gsql -d health_security -f /path/to/consents_schema.sql
gsql -d health_security -f /path/to/access_logs_schema.sql

```

注意：需手动插入测试数据，如：
```
-- 1. 已授权患者（ACTIVE）- 会显示在 Default Authorization 分组
INSERT INTO consents (patient_id, doctor_id, record_scope, status, consent_source) VALUES
(2, 2, 'DEFAULT', 'ACTIVE', 'SYSTEM'),
(3, 2, 'DEFAULT', 'ACTIVE', 'SYSTEM');

-- 2. 待审批患者（PENDING）- 会显示在 Pending Approval 分组
INSERT INTO consents (patient_id, doctor_id, record_scope, status, consent_source, request_reason) VALUES
(4, 2, 'DEFAULT', 'PENDING', 'EXPLICIT_REQUEST', 'Need to review lab results for diagnosis'),
(5, 2, 'DEFAULT', 'PENDING', 'EXPLICIT_REQUEST', 'Requesting access for treatment plan');

-- 3. 已撤销患者（REVOKED）- 会显示在 Revoked 分组
INSERT INTO consents (patient_id, doctor_id, record_scope, status, consent_source) VALUES
(6, 2, 'DEFAULT', 'REVOKED', 'SYSTEM');

-- 验证插入结果
SELECT id, patient_id, doctor_id, status, record_scope FROM consents WHERE doctor_id = 2;
```
#### 如果只是想创建干净数据库

```powershell
.\database\setup_opengauss_copy.ps1 -NoSourceCopy
```

这种方式只会执行 `database/schema.sql` 和 `database/seed_users.sql`，不会包含原数据库中的患者和病历数据。

如果 `5433` 端口被占用，换一个端口，例如：

```powershell
.\database\setup_opengauss_copy.ps1 -HostPort 15432
```

如果已经运行过一次脚本，又想再创建一份新的数据库副本，请换一个新的容器名和端口：

```powershell
.\database\setup_opengauss_copy.ps1 -TargetContainer healthcare-opengauss-copy2 -HostPort 5434
```

检查容器：

```powershell
docker ps
```

进入默认目标容器：

```powershell
docker exec -it healthcare-opengauss-dev bash
```

在容器中连接数据库：

```bash
su - omm
gsql -d health_security
```

查看演示账号：

```sql
SELECT id, username, role, status FROM users;
```

退出：

```sql
\q
```

```bash
exit
exit
```

### 3. 配置后端 `.env`

复制示例配置：

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

如果使用的是别人提供的数据库 dump 文件，请直接使用提供者给你的 `MEDICAL_RECORD_KEY`，不要重新生成。因为 dump 里的病历密文必须用同一把密钥才能解密。

如果是自己初始化干净数据库并重新导入 Synthea 数据，可以生成新的病历加密密钥：

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
[Convert]::ToBase64String($bytes)
```

复制输出的 base64 字符串，或者复制数据库提供者发给你的 `MEDICAL_RECORD_KEY`，打开配置文件：

```powershell
notepad .\backend\.env
```

如果使用数据库脚本默认参数，把 `.env` 改成：

```env
DATABASE_URL=postgresql+psycopg2://omm:OpenGauss%40123@localhost:5433/health_security
JWT_SECRET=dev_secret_for_course_project
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MEDICAL_RECORD_KEY=把base64密钥粘贴到这里
TZ=Asia/Shanghai
```

注意：数据库密码里的 `@` 在 URL 中要写成 `%40`，所以 `OpenGauss@123` 在 `DATABASE_URL` 里写成 `OpenGauss%40123`。

注意：上方DATABASE_URL,JWT_SECRET,一直到TZ 都要改为小写，否则程序无法正常运行；倘若改为小写也无法登录，请查看是否是omm权限导致的，最好新建立一个账户，并更改env。

注意：`MEDICAL_RECORD_KEY` 必须是 base64 编码后的 32 字节密钥。如果数据库里已经有加密病历，换密钥后旧病历将无法解密。

如果同学使用你导出的 dump 文件，里面的 `medical_records.encrypted_data` 也会被复制过去。要让后端正常解密这些病历，同学的 `backend/.env` 必须使用你导入病历时相同的 `MEDICAL_RECORD_KEY`。

如果你用了其他端口，例如 `15432`，则改成：

```env
DATABASE_URL=postgresql+psycopg2://omm:OpenGauss%40123@localhost:15432/health_security
```

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

如果只是想快速跑通 Demo，可以跳过本步骤，直接导入合成病历。

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

### 7. 导入合成病历

如果你已经从数据库 dump 文件恢复了完整数据库，通常可以跳过本步骤，因为 dump 里已经包含患者和加密病历数据。

如果你是用 `-NoSourceCopy` 初始化的干净数据库，或者需要重新导入 Synthea 数据，确认 Docker 容器正在运行、`backend/.env` 已配置、`MEDICAL_RECORD_KEY` 已填写、后端依赖已安装后，执行：

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\import_synthea_records.py
cd ..
```

导入脚本会把导入的患者绑定到患者演示账号。这样使用 `patient1` 到 `patient10` 中已绑定病历的账号登录后，就能看到自己的病历。重复执行时，已导入过的 Synthea 患者会被跳过。

当前本地新版开发库的数据状态：

```text
users: 13
patients: 100
medical_records: 100
```

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
cd D:\VScode-files\Smart-Healthcare-Record-System
cd backend
.\run_dev.ps1
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
cd D:\VScode-files\Smart-Healthcare-Record-System
cd frontend
.\run_dev.ps1
```

前端默认地址：

```text
http://localhost:5173
```

前端启动脚本会在当前 PowerShell 窗口运行 Vite，并在 2 秒后自动打开页面。

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
| `doctor1` | `DOCTOR` | `/doctor` | 登录和页面跳转，占位页 |
| `admin` | `ADMIN` | `/admin` | 登录和页面跳转，占位页 |
| `auditor` | `AUDITOR` | `/auditor` | 登录和页面跳转，占位页 |

## 当前可演示流程

1. 执行 `database/setup_opengauss_copy.ps1` 准备数据库容器。
2. 配置 `backend/.env`，填写数据库连接和 `MEDICAL_RECORD_KEY`。
3. 安装后端依赖和前端依赖。
4. 如有需要，使用 Synthea 生成合成数据。
5. 如果使用的是干净数据库，执行 `backend/scripts/import_synthea_records.py` 导入合成病历；如果已经从 dump 恢复完整数据库，可以跳过导入。
6. 启动后端和前端。
7. 使用 `patient1` 到 `patient10` 中任意已绑定病历的患者账号登录，密码为 `password123`。
8. 进入患者 Dashboard，查看患者基础信息、诊断列表、相关就诊、检查、用药、操作记录。
9. 查询 `medical_records.encrypted_data`，验证病历正文以密文保存。

### 医生端

1. 使用 doctor1 登录，进入医生 Dashboard，查看 “我的病人列表”（5 个分组）。
2. 点击 “搜索患者”，输入患者名称搜索，根据患者授权状态显示智能操作按钮。
3. 对未授权患者，提交 DEFAULT/EXTRA 类型授权申请（填写申请理由）。
4. 申请提交后，患者端会显示待审批申请，医生端患者移至 Pending Approval 分组。
5. 患者批准申请后，医生端患者移至对应分组（Default Access/Full Access）。
6. 点击 “查看病历”，查看按授权范围脱敏后的患者病历内容。
7. 患者撤销授权后，医生端患者移至 Revoked 分组，再次查看病历会被拒绝。
8. 被拒绝的申请可重新提交，已有 Full Access 的患者不显示申请按钮，已有 Default Access 的患者只显示 Apply Full Access 按钮。

### 患者端
1. 使用 patient1-10 登录，进入患者 Dashboard，查看本人病历、统计数据、诊断列表。
2. 切换到 Doctor Authorization Tab，查看待审批授权申请。
3. 对申请进行批准 / 拒绝操作（可填写审批备注）。
4. 查看已授权医生列表，对任意医生执行撤销授权操作。
5. 撤销授权后，对应医生将无法再查看该患者病历。

## 后续待办

- 实现审计日志，记录登录、查看病历、拒绝访问、授权变更等行为。
- 实现审计日志 SHA-256 哈希链和完整性验证接口。
- 补齐管理员、审计员页面的业务功能。
- 准备最终演示脚本和报告截图。

- 成员 D：继续实现 `audit_logs` 表，访问日志、拒绝日志、SHA-256 哈希链和完整性验证页面。
- 所有后端受保护接口都应复用 `get_current_user()` 或 `require_roles()`，不要在各模块重复实现登录认证。

## 参考文档

- [项目设计文档](docs/PROJECT_DESIGN.md)
- [中文计划书](docs/GROUP_PROJECT_PLAN_CN.md)
- [接口边界文档](docs/API_BOUNDARY.md)
