# Smart Healthcare Record System

智慧医疗病历安全系统。项目用于展示电子病历场景中的核心数据安全机制：身份认证、角色权限控制、病历加密存储、医生授权访问、患者授权管理、审计日志哈希链，以及医生写入病历后的隐藏水印校验。

## 项目重点

- 患者病历以结构化 JSON 保存，入库前使用 AES-GCM 加密。
- 医生必须拥有有效授权才能查看或写入患者病历。
- DEFAULT 授权只返回必要范围内的脱敏病历；EXTRA / Full Access 返回完整范围。
- 患者可以查看、批准、拒绝、撤销医生授权。
- 管理员只负责账号、医生审核、医患分配和系统统计，不能查看解密病历正文。
- 审计员可以查看审计日志、验证日志哈希链、检查病历隐藏水印。

## 技术栈

| 模块 | 技术 |
|---|---|
| 前端 | Vue 3, TypeScript, Vite, Element Plus, Pinia, Vue Router |
| 前端 API | Axios 统一实例与请求拦截器 |
| 后端 | FastAPI, SQLAlchemy, Pydantic, Uvicorn |
| 数据库 | openGauss / PostgreSQL compatible driver, psycopg2 |
| 认证 | JWT, bcrypt |
| 病历安全 | AES-GCM 加密, 字段脱敏, HMAC-SHA256 隐藏水印 |
| 审计 | SHA-256 哈希链 |
| 数据来源 | Synthea 合成医疗数据 & 医生手动写入 |

## 角色功能

### Patient

- 登录后查看本人合并病历、诊断、就诊、检查、用药和操作记录。
- 查看可选择的医生，并为医生授予 DEFAULT 访问权限。
- 查看医生提交的授权申请。
- 批准、拒绝或撤销医生访问权限。

### Doctor

- 登录后查看自己的患者列表，按授权状态分组。
- 搜索患者并提交 Default Access 或 Full Access 申请。
- 在有效授权下查看按权限处理后的患者病历。
- 在有效授权下新增医生病历。
- 当前不支持删除整份病历。

### Admin

- 查看系统统计和安全边界提示。
- 创建医生账号。
- 启用、禁用账号，重置密码。
- 审核医生，维护科室、执照号和备注。
- 将患者分配给已审核医生，并生成 14 天 DEFAULT 授权。

### Auditor

- 查看审计统计和审计日志。
- 验证 `audit_logs` 哈希链完整性。
- 查看病历隐藏水印状态，识别缺失、无效或解密失败的记录。

## 主要数据表

| 表 | 说明 |
|---|---|
| `users` | 登录账号、密码哈希、角色和状态 |
| `patients` | 患者基础信息，与患者账号绑定 |
| `doctors` | 医生资料、科室、执照号和审核状态 |
| `medical_records` | 加密病历、nonce、来源、记录类型和写入医生 |
| `consents` | 医生访问授权，包含 DEFAULT / EXTRA 范围 |
| `access_logs` | 医生病历访问或拒绝访问记录 |
| `audit_logs` | 带 SHA-256 哈希链的安全审计日志 |

## 项目结构

```text
Smart-Healthcare-Record-System/
├─ backend/                         后端 FastAPI 服务
│  ├─ app/
│  │  ├─ api/                       业务接口路由
│  │  │  ├─ auth.py                 登录、患者注册、当前用户
│  │  │  ├─ patient_records.py      患者病历与授权管理
│  │  │  ├─ doctor.py               医生患者、授权申请、病历写入
│  │  │  ├─ admin.py                管理员账号、医生审核、医患分配
│  │  │  └─ auditor.py              审计日志、哈希链、水印验证
│  │  ├─ core/                      配置、JWT、RBAC、时区工具
│  │  ├─ db/                        数据库连接和启动初始化
│  │  ├─ models/                    SQLAlchemy 数据表模型
│  │  ├─ schemas/                   Pydantic 请求/响应结构
│  │  └─ services/                  业务服务与安全能力
│  │     ├─ audit_service.py        审计日志与哈希链
│  │     ├─ clinical_records.py     临床记录归一化、关联和科室分类
│  │     ├─ consent_access.py       授权状态与优先级
│  │     ├─ crypto_service.py       病历 AES-GCM 加解密
│  │     ├─ doctor_display.py       医生名称与科室显示辅助
│  │     ├─ record_presentation.py  病历展示、脱敏、去重、DEFAULT/EXTRA 组装
│  │     └─ record_watermark.py     隐藏水印嵌入与验证
│  ├─ scripts/
│  │  └─ import_synthea_records.py  Synthea FHIR 数据导入脚本
│  ├─ .env.example                  后端环境变量模板
│  ├─ requirements.txt              后端依赖
│  └─ run_dev.ps1                   后端本地启动脚本
│
├─ frontend/                        前端 Vue 应用
│  ├─ src/
│  │  ├─ api/                       后端 API 封装
│  │  │  ├─ client.ts               统一 Axios 实例
│  │  │  ├─ auth.ts                 登录、注册、当前用户
│  │  │  ├─ patientRecords.ts       患者病历接口
│  │  │  ├─ patientAuth.ts          患者授权接口
│  │  │  ├─ doctor.ts               医生业务接口
│  │  │  ├─ admin.ts                管理员接口
│  │  │  └─ auditor.ts              审计员接口
│  │  ├─ components/                公共组件
│  │  ├─ layouts/                   Dashboard 通用布局
│  │  ├─ router/                    路由与角色守卫
│  │  ├─ stores/                    Pinia 登录状态
│  │  └─ views/                     登录页、患者/医生/管理员/审计员页面
│  ├─ package.json                  前端依赖和脚本
│  └─ run_dev.ps1                   前端本地启动脚本
│
├─ database/                        数据库脚本和演示数据准备
│  ├─ schema.sql                    表结构
│  ├─ seed_users.sql                默认账号
│  ├─ seed_demo_core.sql            默认医生资料和授权关系
│  ├─ health_security_data_sync.sql 团队统一数据快照
│  └─ setup_demo_database.ps1       一键准备 openGauss 和演示数据
│
├─ synthea/                         合成医疗数据
│  ├─ synthea-with-dependencies.jar Synthea 生成工具
│  └─ output/                       示例 FHIR JSON / CSV 输出
│
├─ docs/                            项目设计文档和 ER 图
└─ README.md                        项目说明
```

## 快速运行

### 1. 配置后端环境变量

将 `backend/.env.example` 的内容复制到 `backend/.env` 中，然后按本机环境修改配置。

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

核心配置如下：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@127.0.0.1:5433/health_security
JWT_SECRET=replace_with_your_own_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MEDICAL_RECORD_KEY=replace_with_base64_32_byte_key
TZ=Asia/Shanghai
```

`MEDICAL_RECORD_KEY` 必须是 base64 编码后的 32 字节密钥。数据库已有加密病历时，不要随意更换该密钥，否则旧病历无法解密。

### 2. 准备数据库和演示数据

```powershell
.\database\setup_demo_database.ps1 -TargetContainer healthcare-opengauss-dev -HostPort 5433
```

如果要使用团队统一数据快照：

```powershell
.\database\setup_demo_database.ps1 `
  -TargetContainer healthcare-opengauss-dev `
  -HostPort 5433 `
  -DataOnlyDumpFile .\database\health_security_data_sync.sql
```

使用数据快照时，只要快照中的病历是用当前 `MEDICAL_RECORD_KEY` 加密的，旧病例展示、科室分类、DEFAULT/EXTRA 授权展示仍然可用。

### 3. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

前端地址：

```text
http://127.0.0.1:5173
```

## 演示账号

默认密码均为：

```text
password123
```

| 用户名 | 角色 | 页面 | 用途 |
|---|---|---|---|
| `patient1` - `patient10` | PATIENT | `/patient` | 查看本人病历和管理医生授权 |
| `doctor1` - `doctor8` | DOCTOR | `/doctor` | 查看患者、申请授权、新增病历 |
| `admin` | ADMIN | `/admin` | 管理账号、审核医生、分配医患关系 |
| `auditor` | AUDITOR | `/auditor` | 查看审计日志、验证哈希链和检查水印 |

## 关键安全边界

- 数据库中不保存明文病历正文。
- 医生访问病历前必须通过角色、账号状态、医生审核状态和授权有效期校验。
- DEFAULT 授权返回有限范围并脱敏；EXTRA 授权返回完整范围。
- 患者只能访问与自己账号绑定的病历。
- 管理员不能解密查看病历正文。
- 审计日志使用哈希链记录关键行为，便于发现日志篡改。
- 医生新增病历时会嵌入隐藏水印，用于后续追踪来源和辅助校验完整性。

## 常用接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/login` | 登录 |
| `POST` | `/api/auth/register` | 患者注册 |
| `GET` | `/api/auth/me` | 当前用户 |
| `GET` | `/api/patient/me/records/combined` | 患者查看合并病历 |
| `GET` | `/api/patient/me/records/pending-consents` | 患者查看待审批授权 |
| `GET` | `/api/patient/me/records/available-doctors` | 患者查看可选择医生 |
| `POST` | `/api/patient/me/records/default-doctors` | 患者选择默认医生 |
| `POST` | `/api/patient/me/records/consents/{id}/approve` | 患者批准授权 |
| `POST` | `/api/patient/me/records/consents/{id}/reject` | 患者拒绝授权 |
| `POST` | `/api/patient/me/records/consents/{id}/revoke` | 患者撤销授权 |
| `GET` | `/api/doctor/me` | 医生资料 |
| `GET` | `/api/doctor/my-patients` | 医生查看患者列表 |
| `GET` | `/api/doctor/search-patients` | 医生搜索患者 |
| `POST` | `/api/doctor/access-requests` | 医生提交授权申请 |
| `GET` | `/api/doctor/patients/{patient_id}/records` | 医生查看授权病历 |
| `POST` | `/api/doctor/patients/{patient_id}/records` | 医生新增病历 |
| `GET` | `/api/admin/overview` | 管理员系统概览 |
| `GET` | `/api/admin/users` | 管理员查看用户 |
| `GET` | `/api/admin/doctors` | 管理员查看医生 |
| `GET` | `/api/admin/patients` | 管理员查看患者 |
| `POST` | `/api/admin/assignments` | 管理员分配医生患者关系 |
| `GET` | `/api/auditor/summary` | 审计员统计 |
| `GET` | `/api/auditor/audit-logs` | 审计员查看审计日志 |
| `GET` | `/api/auditor/verify-hash-chain` | 审计员验证日志哈希链 |
| `GET` | `/api/auditor/record-watermarks` | 审计员查看病历水印状态 |
