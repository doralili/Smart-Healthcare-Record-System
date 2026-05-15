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

- 首页展示“我的病人列表”
- 病人按状态分组：默认授权、额外授权待审批、已过期、已撤销
- 默认授权病人可直接查看默认范围内的必要病历信息
- 超出默认范围的内容需要提交额外授权申请
- 患者撤销授权后，医生再次访问会被拒绝

### 患者端

- 查看自己的病历
- 查看哪些医生拥有默认访问权限
- 查看医生额外访问申请
- 审批或拒绝额外授权
- 随时撤销医生访问权限
- 查看自己的访问日志

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
| ORM | SQLAlchemy 2.x 或 SQLModel |
| 数据库驱动 | `psycopg2` / `psycopg` 等 PostgreSQL 兼容驱动 |
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
| `doctors` | 医生信息、科室、执照号、审核状态 |
| `medical_records` | 加密后的病历数据、IV、认证标签、加密数据密钥 |
| `consents` | 默认临床授权、额外访问申请与患者撤销记录 |
| `audit_logs` | 安全审计日志和哈希链字段 |

## 最小演示目标

- 数据库中病历是密文，不能直接看到明文医疗内容
- 医生首页展示“我的病人列表”
- 医生可查看默认授权范围内的病历内容
- 医生申请查看默认范围之外的内容时，需要患者额外审批
- 患者撤销授权后，医生再次访问对应病历范围会被拒绝
- 每一次访问和拒绝访问都会写入审计日志
- 审计员可以验证日志哈希链完整性
- 手动篡改旧日志后，系统能检测出异常

## 项目结构

```text
group project/
├── backend/        # 后端 FastAPI 服务代码
├── frontend/       # 前端 Vue 3 页面代码
├── docs/           # 项目设计、计划书等文档
├── scripts/        # 数据导入、初始化等辅助脚本
├── database/       # 数据库设计与初始化文件
├── synthea/        # Synthea 合成医疗数据生成器
└── README.md       # 项目首页说明
```

## 当前实现进度

| 模块 | 状态 | 负责人 | 说明 |
|---|---|---|---|
| 项目初始化 | 已完成 | 成员 A | 已建立 FastAPI 后端、Vue 3 前端、基础目录结构和开发启动脚本 |
| 登录与角色权限 | 已完成 | 成员 A | 已实现 bcrypt 密码哈希、JWT 登录、当前用户识别和基础 RBAC |
| openGauss 数据库连接 | 已完成 | 成员 A | 已配置 openGauss Docker 容器、`users` 表和演示账号 |
| Synthea 数据导入 | 待填写 | 待填写 | 待填写 |
| 病历加密存储 | 待填写 | 待填写 | 待填写 |
| 医生“我的病人列表” | 待填写 | 待填写 | 待填写 |
| 默认授权与撤销 | 待填写 | 待填写 | 待填写 |
| 额外授权申请 | 待填写 | 待填写 | 待填写 |
| 审计日志 | 待填写 | 待填写 | 待填写 |
| 哈希链完整性验证 | 待填写 | 待填写 | 待填写 |
| 前端页面 | 部分完成 | 成员 A | 已完成登录页、四类角色 Dashboard、角色跳转和退出登录 |
| 演示脚本与报告材料 | 待填写 | 待填写 | 待填写 |

## 待办事项

- [x] 初始化 FastAPI 后端项目
- [x] 初始化 Vue 3 前端项目
- [x] 配置 openGauss 数据库连接
- [x] 建立基础数据表
- [x] 实现 JWT 登录认证
- [x] 实现角色权限控制
- [ ] 生成并导入 Synthea 合成数据
- [ ] 实现病历 AES-GCM 加密入库
- [ ] 实现医生“我的病人列表”
- [ ] 实现默认授权、额外授权和撤销授权
- [ ] 实现字段脱敏策略
- [ ] 实现审计日志
- [ ] 实现审计日志哈希链验证
- [ ] 准备最终演示数据和演示脚本

## 运行方式

以下命令默认在项目根目录 `group project/` 下执行。

### 首次环境准备

后端依赖安装：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果 PowerShell 禁止运行 `.ps1` 脚本，可对当前用户启用本地脚本：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

前端依赖安装：

```powershell
cd frontend
npm.cmd install
```

### 后端

1. 启动 openGauss 容器：

```powershell
docker start my_opengauss
```

2. 进入后端目录并启动 FastAPI：

```powershell
cd backend
.\run_dev.ps1
```

后端默认地址：

```text
http://127.0.0.1:8000
```

### 前端

进入前端目录并启动 Vite：

```powershell
cd frontend
.\run_dev.ps1
```

前端默认地址：

```text
http://localhost:5173
```

前端启动脚本会在当前 PowerShell 窗口运行 Vite，并在 2 秒后自动打开前端页面。

### 数据库

当前开发环境使用 Docker 中的 openGauss 容器：

```powershell
docker start my_opengauss
docker exec -it my_opengauss bash
```

进入容器后切换到 openGauss 用户：

```bash
su - omm
gsql -d health_security
```

查看演示账号：

```sql
SELECT id, username, role, status FROM users;
```

### 环境配置

后端需要在 `backend/.env` 中配置数据库连接和 JWT 密钥。示例见 `backend/.env.example`。

```env
DATABASE_URL=postgresql+psycopg2://lxt:your_password@localhost:5432/health_security
JWT_SECRET=dev_secret_for_course_project
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

注意：`.env` 不应提交到 Git；每台电脑需要按自己的数据库用户名和密码配置。

### Synthea 合成数据

Synthea 位于项目内的 `synthea/` 目录，用于生成合成患者和病历数据，避免使用真实医疗隐私数据。

Synthea 需要 Java JDK 17 或更新版本。Windows 下可先检查：

```powershell
java -version
```

生成少量演示数据：

```powershell
cd synthea
.\run_synthea.bat -p 10 --exporter.fhir.export=true --exporter.csv.export=true
```

常用参数说明：

```text
-p 10                         生成 10 个合成患者
--exporter.fhir.export=true   输出 FHIR JSON 数据
--exporter.csv.export=true    输出 CSV 数据
```

生成结果默认位于：

```text
synthea/output/fhir/
synthea/output/csv/
```

成员 B 后续导入时，建议优先读取以下资源：

```text
Patient
Encounter
Condition
Observation
MedicationRequest
Procedure
```

导入目标是将 Synthea 原始数据转换为系统内部的结构化病历 JSON，再加密写入 `medical_records` 表。当前仓库尚未实现 Synthea 导入脚本和病历加密入库逻辑。

## 演示账号

所有演示账号的密码均为：

```text
password123
```

| 用户名 | 角色 | 登录后页面 |
|---|---|---|
| `patient1` | 患者 `PATIENT` | `/patient` |
| `doctor1` | 医生 `DOCTOR` | `/doctor` |
| `admin` | 管理员 `ADMIN` | `/admin` |
| `auditor` | 审计员 `AUDITOR` | `/auditor` |

密码以 bcrypt 哈希形式保存在 `users.password_hash` 字段中，数据库中不保存明文密码。

## 接口文档

后端启动后可访问 FastAPI 自动生成的 Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

## 成员接手说明

- 成员 B：继续实现 `patients`、`medical_records` 表，Synthea 数据解析脚本，AES-GCM 加密入库和解密服务。
- 成员 C：继续实现 `doctors`、`consents` 表，医生病人列表、默认授权、额外授权申请、患者审批/拒绝/撤销和字段脱敏。
- 成员 D：继续实现 `audit_logs` 表，访问日志、拒绝日志、SHA-256 哈希链和完整性验证页面。
- 所有后端受保护接口都应复用 `get_current_user()` 或 `require_roles()`，不要在各模块重复实现登录认证。

## 参考文档

- [项目设计文档](docs/PROJECT_DESIGN.md)
- [中文计划书](docs/GROUP_PROJECT_PLAN_CN.md)
- [接口边界文档](docs/API_BOUNDARY.md)
