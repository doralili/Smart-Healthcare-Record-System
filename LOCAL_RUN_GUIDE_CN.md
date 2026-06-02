# 本机运行傻瓜式说明

这份说明只针对当前本机开发环境。`.env`、虚拟环境、前端依赖、数据库 dump 都是本地文件，不需要上传 GitHub。

## 0. 先确认项目位置

项目目录是：

```powershell
D:\Codex项目\医疗系统\Smart-Healthcare-Record-System
```

后续命令默认都在 PowerShell 里执行。

## 1. 每次运行前先启动 Docker Desktop

先打开 Docker Desktop，等它启动完成。

然后进入项目目录：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System
```

检查数据库容器是否在运行：

```powershell
docker ps
```

如果没有看到 `healthcare-opengauss-dev`，执行：

```powershell
docker start healthcare-opengauss-dev
```

再确认一次：

```powershell
docker ps
```

看到类似下面这一行就说明数据库容器起来了：

```text
healthcare-opengauss-dev   0.0.0.0:5433->5432/tcp
```

## 2. 确认后端配置文件

后端配置文件在：

```text
backend\.env
```

这个文件不要上传 GitHub。

当前本机应该是：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@localhost:5433/health_security
JWT_SECRET=dev_secret_for_course_project
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MEDICAL_RECORD_KEY=rvlc43/VxbvHAOMDYRZ7IyG1PqRDFvEo7hbClSmmqxc=
TZ=Asia/Shanghai
```

注意：

- 这里用 `healthcare` 用户，不用 README 里的 `omm` 用户。
- 原因是当前 openGauss 镜像禁止 `omm` 从容器外连接数据库。
- `Healthcare%40123` 里的 `%40` 表示密码里的 `@`。
- `MEDICAL_RECORD_KEY` 必须保持不变，否则已有加密病历无法解密。

## 3. 启动后端

新开一个 PowerShell 窗口，执行：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

看到类似下面内容，说明后端启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
```

不要关闭这个 PowerShell 窗口。

检查后端是否正常：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing
```

如果返回里有：

```json
{"status":"ok"}
```

就说明后端正常。

后端接口文档地址：

```text
http://127.0.0.1:8000/docs
```

## 4. 启动前端

再新开一个 PowerShell 窗口，执行：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\frontend
"C:\Program Files\nodejs\npm.cmd" run dev
```

看到类似下面内容，说明前端启动成功：

```text
Local: http://localhost:5173/
```

不要关闭这个 PowerShell 窗口。

如果 `npm.cmd` 可以直接识别，也可以用：

```powershell
npm run dev
```

## 5. 打开系统

浏览器打开：

```text
http://127.0.0.1:5173
```

或：

```text
http://localhost:5173
```

## 6. 登录账号

患者账号：

```text
用户名：patient1
密码：password123
```

`patient1` 到 `patient10` 都可以试，密码都是：

```text
password123
```

其他演示账号：

```text
doctor1  / password123
admin    / password123
auditor  / password123
```

目前可以演示：

- 患者端病历查看
- 患者端医生授权审批、拒绝、撤销
- 医生端搜索患者、提交授权申请、查看脱敏病历
- 审计员端查看审计日志和验证哈希链

管理员页面目前还是占位页。系统保留数据库里的 `ADMIN` 角色和 `admin` 种子账号，但当前核心演示不依赖管理员功能。

如果后续真的要做管理员功能，比较合理的范围是用户管理，例如查看用户、启用/禁用账号、创建医生或审计员账号。当前版本不做删除账号功能，避免影响审计和历史记录。

## 6.1 推荐演示顺序

1. 使用 `doctor1 / password123` 登录。
2. 进入医生端 Search Patients，搜索患者姓名。
3. 对某个患者提交 Default Access 或 Full Access 申请。
4. 退出登录，使用对应患者账号登录，例如 `patient1 / password123`。
5. 进入 Doctor Authorization，批准或拒绝医生申请。
6. 再使用 `doctor1` 登录，查看 My Patients 分组变化。
7. 如果授权已批准，点击 View Record 查看脱敏病历。
8. 再使用患者账号撤销授权。
9. 使用 `doctor1` 再次访问该患者病历，应被拒绝。
10. 最后使用 `auditor / password123` 登录。
11. 在 Auditor Dashboard 查看审计日志，并点击 Verify Hash Chain。

## 7. 如果后端连不上数据库

先确认 Docker 容器在运行：

```powershell
docker ps
```

如果容器没启动：

```powershell
docker start healthcare-opengauss-dev
```

然后重新启动后端。

如果后端日志里出现：

```text
Forbid remote connection with initial user
```

说明 `.env` 又改回了 `omm` 用户。把 `DATABASE_URL` 改回：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@localhost:5433/health_security
```

## 8. 如果前端命令找不到 npm

优先使用完整路径：

```powershell
"C:\Program Files\nodejs\npm.cmd" run dev
```

如果还是不行，重新打开 PowerShell 再试。

## 9. 如果要完全重新恢复数据库

数据库 dump 文件本机位置是：

```text
database\health_security.copy.sql
```

这个文件不要上传 GitHub。

通常不需要重新恢复。只有数据库坏了或容器被删了才需要。

如果真的要重建，需要先删除旧容器或换一个新容器名。不要随便删除不认识的 Docker 容器。

## 9.1 如果审计页面打不开或提示缺表

新版需要这些表：

```text
consents
access_logs
audit_logs
```

后端启动时会自动创建 `audit_logs` 表。如果 `consents` 或 `access_logs` 缺失，说明你的数据库 dump 太旧，建议换最新版 `database\health_security.copy.sql` 后重新恢复数据库。

审计日志会记录：

```text
LOGIN
PATIENT_REGISTER
CONSENT_REQUEST
CONSENT_APPROVE
CONSENT_REJECT
CONSENT_REVOKE
VIEW_RECORD
PATIENT_VIEW_OWN_RECORD
```

审计员页面的 Verify Hash Chain 会检查 `audit_logs.previous_hash` 和 `audit_logs.current_hash` 是否连续且未被篡改。

## 9.2 手动篡改旧日志，演示哈希链断裂

这个步骤用于演示“有人改了旧审计日志后，系统能发现异常”。

先确认数据库容器正在运行：

```powershell
docker ps
```

如果没运行：

```powershell
docker start healthcare-opengauss-dev
```

进入 openGauss 容器：

```powershell
docker exec -it healthcare-opengauss-dev bash
```

切换到数据库用户：

```bash
su - omm
```

说明：

- `omm` 是 openGauss 容器里的数据库系统用户，适合用来进容器后执行 `gsql`。
- 但后端程序平时不是用 `omm` 连数据库，而是用 `.env` 里的 `healthcare` 用户。
- 现在这套恢复后的本机数据库，表仍然在默认 `public` 里，所以手动查审计日志直接写 `audit_logs`。

进入项目数据库：

```bash
gsql -d health_security
```

先看当前审计日志：

```sql
SELECT id, action, outcome, current_hash
FROM audit_logs
ORDER BY id
LIMIT 5;
```

注意：`healthcare` 是后端连接数据库的用户，不代表表名也要写成 `healthcare.audit_logs`。当前本机恢复方案里，手动 SQL 使用 `audit_logs`。

手动篡改第 1 条日志。比如把 `outcome` 改成一个假的值：

```sql
UPDATE audit_logs
SET outcome = 'TAMPERED'
WHERE id = 1;
```

退出数据库和容器：

```sql
\q
```

```bash
exit
exit
```

然后回到浏览器，使用：

```text
auditor / password123
```

进入 Auditor Dashboard，点击：

```text
Verify Hash Chain
```

这时应该看到类似：

```text
Audit chain broken at log #1: current_hash mismatch
```

这就是正确的演示效果：旧日志内容被改了，但 `current_hash` 没跟着变，所以系统检测出篡改。

如果想恢复成正常状态，最简单的办法是重新恢复数据库 dump。注意：不要在正式演示前乱改生产/展示数据库，建议只在演示防篡改时做这一步。

## 9.3 篡改演示后恢复哈希链正常

如果你只是按上一节的示例执行了：

```sql
UPDATE audit_logs
SET outcome = 'TAMPERED'
WHERE id = 1;
```

那么恢复也很简单，把第 1 条改回原值：

```powershell
docker exec -it healthcare-opengauss-dev bash
```

```bash
su - omm
gsql -d health_security
```

执行：

```sql
UPDATE audit_logs
SET outcome = 'SUCCESS'
WHERE id = 1;
```

退出：

```sql
\q
```

```bash
exit
exit
```

然后刷新 Auditor Dashboard，重新点击：

```text
Verify Hash Chain
```

应该恢复为：

```text
Valid
```

注意：这个恢复方法只适用于你确实只改了 `audit_logs` 里 `id = 1` 的 `outcome` 字段。如果你改了别的字段，或者改了多条日志，最稳妥的恢复方式是重新恢复数据库 dump。

## 9.4 如果提示 audit_logs 不存在

如果你执行：

```sql
SELECT * FROM audit_logs;
```

看到：

```text
relation "audit_logs" does not exist
```

先不要急着恢复数据库。确认你已经进入了正确数据库：

```sql
\c health_security
```

然后再查：

```sql
SELECT id, action, outcome, current_hash
FROM audit_logs
ORDER BY id
LIMIT 5;
```

如果还是不存在，说明新版后端还没有创建审计表。回到项目根目录，执行一次：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\backend
.\.venv\Scripts\python.exe -c "from app.db.init_db import ensure_audit_schema; ensure_audit_schema(); print('schema ensured')"
```

然后重新启动后端，再进入 Auditor Dashboard 操作几次，审计日志才会产生。

## 9.5 重新恢复数据库 dump

只有在下面这种情况才需要恢复 dump：

- 你手动改错了多条审计日志。
- 你忘了原来的字段值，没法用 `UPDATE` 改回去。
- 数据库被你试验弄乱了，网页演示已经不正常。

恢复 dump 会把当前本机数据库容器重建，原来容器里的测试数据会丢失。确认要恢复后，按下面做。

### 第 1 步：确认 dump 文件在正确位置

项目使用这个文件作为恢复来源：

```text
database\health_security.copy.sql
```

也就是完整路径类似：

```text
D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\database\health_security.copy.sql
```

如果这个文件不存在，先把你保存的 `.sql` dump 文件复制到 `database` 文件夹，并改名为：

```text
health_security.copy.sql
```

### 第 2 步：停止后端

如果后端正在运行，先在后端终端按：

```text
Ctrl + C
```

### 第 3 步：删除旧数据库容器

在项目根目录执行：

```powershell
docker stop healthcare-opengauss-dev
docker rm healthcare-opengauss-dev
```

如果提示容器不存在，说明它已经被删掉了，可以继续下一步。

### 第 4 步：用 dump 重建数据库容器

在项目根目录执行：

```powershell
.\database\setup_opengauss_copy.ps1 -DumpFilePath .\database\health_security.copy.sql
```

这一步会重新创建：

```text
healthcare-opengauss-dev
```

并把 dump 里的数据导入 `health_security` 数据库。

### 第 5 步：重新创建本机后端使用的 healthcare 用户

因为你本机 `.env` 使用的是：

```env
DATABASE_URL=postgresql+psycopg2://healthcare:Healthcare%40123@localhost:5433/health_security
```

所以重建容器后，还要重新创建 `healthcare` 数据库用户。

注意：这里只创建数据库连接用户，不创建 `healthcare` schema。表仍然放在默认 `public` 里，后面手动 SQL 直接查 `audit_logs`。

进入容器：

```powershell
docker exec -it healthcare-opengauss-dev bash
```

切换用户并进入数据库：

```bash
su - omm
gsql -d health_security
```

执行：

```sql
CREATE USER healthcare WITH PASSWORD 'Healthcare@123';
GRANT ALL PRIVILEGES ON DATABASE health_security TO healthcare;
GRANT USAGE, CREATE ON SCHEMA public TO healthcare;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO healthcare;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO healthcare;
```

退出：

```sql
\q
```

```bash
exit
exit
```

### 第 6 步：让新版后端补齐审计表

回到后端目录：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\backend
```

执行：

```powershell
.\.venv\Scripts\python.exe -c "from app.db.init_db import ensure_audit_schema; ensure_audit_schema(); print('schema ensured')"
```

### 第 7 步：重新启动后端和前端

后端：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd D:\Codex项目\医疗系统\Smart-Healthcare-Record-System\frontend
npm run dev
```

然后重新登录网页测试。恢复 dump 后，之前手动篡改造成的哈希链错误应该消失；如果你又执行了新的篡改 SQL，审计员页面会再次报错，这是正常演示效果。

## 10. Git 提交前检查

提交前执行：

```powershell
git status --short
```

正常情况下，本地运行产生的这些东西不会显示出来：

```text
backend\.env
backend\.venv
frontend\node_modules
database\health_security.copy.sql
*.log
```

因为它们已经被 `.gitignore` 忽略。

如果 `git status --short` 没输出，说明没有东西会被提交。
