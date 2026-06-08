param(
    [string]$TargetContainer = "healthcare-opengauss-dev",
    [string]$DatabaseName = "health_security",
    [string]$Image = "opengauss/opengauss:latest",
    [int]$HostPort = 5433,
    [string]$DbSecret = "OpenGauss@123",
    [string]$AppUser = "healthcare",
    [string]$AppPassword = "Healthcare@123",
    [string]$EnvPath = "",
    [string]$MedicalRecordKey = "",
    [string]$JwtSecret = "",
    [string]$PythonExe = "",
    [string]$DataOnlyDumpFile = "",
    [switch]$SkipSyntheaImport
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$DefaultEnvFile = Join-Path $BackendDir ".env"
$SchemaFile = Join-Path $PSScriptRoot "schema.sql"
$SeedUsersFile = Join-Path $PSScriptRoot "seed_users.sql"
$SeedCoreFile = Join-Path $PSScriptRoot "seed_demo_core.sql"

function Write-Step {
    param([string]$Message)
    Write-Output ""
    Write-Output "==> $Message"
}

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -le 0) {
            continue
        }

        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $values[$key] = $value
    }

    return $values
}

function Invoke-OpenGauss {
    param(
        [string]$ContainerName,
        [string]$Command
    )

    Invoke-Docker exec -u omm $ContainerName bash -lc "source /home/omm/.bashrc; $Command"
}

function Read-OpenGauss {
    param(
        [string]$ContainerName,
        [string]$Command
    )

    $output = & docker exec -u omm $ContainerName bash -lc "source /home/omm/.bashrc; $Command"
    if ($LASTEXITCODE -ne 0) {
        throw "openGauss command failed in container '$ContainerName': $Command"
    }
    return $output
}

function Test-ContainerExists {
    param([string]$Name)

    $names = & docker ps -a --format "{{.Names}}"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list Docker containers."
    }
    return @($names) -contains $Name
}

function Test-ContainerRunning {
    param([string]$Name)

    $names = & docker ps --format "{{.Names}}"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list running Docker containers."
    }
    return @($names) -contains $Name
}

function Wait-OpenGaussReady {
    param([string]$Name)

    Write-Step "Waiting for openGauss to accept connections"
    for ($i = 1; $i -le 60; $i++) {
        & docker exec -u omm $Name bash -lc "source /home/omm/.bashrc; gsql -d postgres -c 'SELECT 1;'" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Output "openGauss is ready."
            return
        }

        Start-Sleep -Seconds 2
    }
    throw "openGauss did not become ready in time."
}

function Invoke-GsqlFile {
    param(
        [string]$LocalFile,
        [string]$ContainerFile
    )

    if (-not (Test-Path $LocalFile)) {
        throw "Missing SQL file: $LocalFile"
    }

    Invoke-Docker cp $LocalFile "${TargetContainer}:$ContainerFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $ContainerFile"
}

function Invoke-GsqlText {
    param(
        [string]$Sql,
        [string]$DbName = $DatabaseName
    )

    $tempFile = Join-Path $env:TEMP ("healthcare_seed_" + [guid]::NewGuid().ToString("N") + ".sql")
    $containerFile = "/tmp/" + (Split-Path -Leaf $tempFile)

    try {
        Set-Content -LiteralPath $tempFile -Value $Sql -Encoding UTF8
        Invoke-Docker cp $tempFile "${TargetContainer}:$containerFile"
        Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DbName -f $containerFile"
    }
    finally {
        if (Test-Path $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}

function Read-GsqlText {
    param(
        [string]$Sql,
        [string]$DbName = $DatabaseName
    )

    $tempFile = Join-Path $env:TEMP ("healthcare_read_" + [guid]::NewGuid().ToString("N") + ".sql")
    $containerFile = "/tmp/" + (Split-Path -Leaf $tempFile)

    try {
        Set-Content -LiteralPath $tempFile -Value $Sql -Encoding UTF8
        Invoke-Docker cp $tempFile "${TargetContainer}:$containerFile"
        $output = & docker exec -u omm $TargetContainer bash -lc "source /home/omm/.bashrc; gsql -d $DbName -t -A -f $containerFile"
        if ($LASTEXITCODE -ne 0) {
            throw "openGauss SQL failed in container '$TargetContainer': $Sql"
        }
        return $output
    }
    finally {
        if (Test-Path $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}

function Invoke-Gsql {
    param([string]$Sql)

    Invoke-GsqlText -Sql $Sql -DbName $DatabaseName
}

function Restore-DataOnlyDump {
    param([string]$LocalFile)

    if (-not (Test-Path $LocalFile)) {
        throw "Missing data-only dump file: $LocalFile"
    }

    $resolvedFile = (Resolve-Path -LiteralPath $LocalFile).Path
    $containerFile = "/tmp/" + (Split-Path -Leaf $resolvedFile)

    Write-Step "Clearing existing business table data"
    Invoke-Gsql @"
TRUNCATE TABLE
    access_logs,
    audit_logs,
    consents,
    doctors,
    medical_records,
    patients,
    users
RESTART IDENTITY CASCADE;
"@

    Write-Step "Restoring synchronized business data"
    Invoke-Docker cp $resolvedFile "${TargetContainer}:$containerFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $containerFile"
}

if ($DatabaseName -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    throw "DatabaseName must contain only letters, numbers, and underscores, and cannot start with a number."
}
if ($AppUser -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    throw "AppUser must contain only letters, numbers, and underscores, and cannot start with a number."
}

if (-not $EnvPath) {
    $EnvPath = $DefaultEnvFile
}

$envValues = Read-DotEnv -Path $EnvPath
if (-not $JwtSecret -and $envValues.ContainsKey("JWT_SECRET")) {
    $JwtSecret = $envValues["JWT_SECRET"]
}
if (-not $MedicalRecordKey -and $envValues.ContainsKey("MEDICAL_RECORD_KEY")) {
    $MedicalRecordKey = $envValues["MEDICAL_RECORD_KEY"]
}
if (-not $JwtSecret) {
    throw "JWT_SECRET was not provided and could not be read from $EnvPath"
}
if (-not $MedicalRecordKey -and -not $SkipSyntheaImport) {
    throw "MEDICAL_RECORD_KEY was not provided and could not be read from $EnvPath"
}

Write-Step "Preparing openGauss container '$TargetContainer'"
if (Test-ContainerExists $TargetContainer) {
    if (Test-ContainerRunning $TargetContainer) {
        Write-Output "Container is already running."
    }
    else {
        Invoke-Docker start $TargetContainer
    }
}
else {
    Invoke-Docker run `
        --name $TargetContainer `
        -d `
        -e "GS_PASSWORD=$DbSecret" `
        -p "${HostPort}:5432" `
        $Image
}

Wait-OpenGaussReady $TargetContainer

Write-Step "Ensuring database '$DatabaseName' exists"
$databaseExists = Read-GsqlText -DbName "postgres" -Sql "SELECT 1 FROM pg_database WHERE datname='$DatabaseName';"
if (@($databaseExists) -contains "1") {
    Write-Output "Database already exists."
}
else {
    Invoke-GsqlText -DbName "postgres" -Sql "CREATE DATABASE $DatabaseName;"
}

Write-Step "Applying schema"
# schema.sql uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
Invoke-GsqlFile -LocalFile $SchemaFile -ContainerFile "/tmp/schema.sql"

if (-not $DataOnlyDumpFile) {
    Write-Step "Applying demo user seed"
    # seed_users.sql uses INSERT ... WHERE NOT EXISTS.
    Invoke-GsqlFile -LocalFile $SeedUsersFile -ContainerFile "/tmp/seed_users.sql"
}
else {
    Write-Output "DataOnlyDumpFile was provided. Demo user seed will be skipped."
}

Write-Step "Ensuring backend database user '$AppUser'"
$roleExists = Read-GsqlText -DbName "postgres" -Sql "SELECT 1 FROM pg_roles WHERE rolname='$AppUser';"
if (@($roleExists) -contains "1") {
    Write-Output "Role '$AppUser' already exists."
}
else {
    $escapedPassword = $AppPassword.Replace("'", "''")
    Invoke-GsqlText -DbName "postgres" -Sql "CREATE USER $AppUser WITH PASSWORD '$escapedPassword';"
}

Invoke-GsqlText -Sql @"
ALTER USER $AppUser SET search_path TO public;
GRANT ALL PRIVILEGES ON DATABASE $DatabaseName TO $AppUser;
GRANT USAGE, CREATE ON SCHEMA public TO $AppUser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $AppUser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $AppUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO $AppUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO $AppUser;
"@

$encodedPassword = [System.Uri]::EscapeDataString($AppPassword)
$databaseUrl = "postgresql+psycopg2://${AppUser}:$encodedPassword@127.0.0.1:$HostPort/$DatabaseName"

if ($DataOnlyDumpFile) {
    Restore-DataOnlyDump -LocalFile $DataOnlyDumpFile
}
elseif (-not $SkipSyntheaImport) {
    Write-Step "Importing Synthea patients and encrypted medical records"
    Push-Location $BackendDir
    try {
        if (-not $PythonExe) {
            $venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
            if (Test-Path $venvPython) {
                $PythonExe = $venvPython
            }
            else {
                $PythonExe = "python"
            }
        }

        $oldDatabaseUrl = $env:DATABASE_URL
        $oldJwtSecret = $env:JWT_SECRET
        $oldJwtAlgorithm = $env:JWT_ALGORITHM
        $oldExpire = $env:ACCESS_TOKEN_EXPIRE_MINUTES
        $oldMedicalKey = $env:MEDICAL_RECORD_KEY
        $oldTz = $env:TZ

        try {
            $env:DATABASE_URL = $databaseUrl
            $env:JWT_SECRET = $JwtSecret
            $env:JWT_ALGORITHM = "HS256"
            $env:ACCESS_TOKEN_EXPIRE_MINUTES = "60"
            $env:MEDICAL_RECORD_KEY = $MedicalRecordKey
            $env:TZ = "Asia/Shanghai"

            & $PythonExe ".\scripts\import_synthea_records.py"
            if ($LASTEXITCODE -ne 0) {
                throw "Synthea import failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            $env:DATABASE_URL = $oldDatabaseUrl
            $env:JWT_SECRET = $oldJwtSecret
            $env:JWT_ALGORITHM = $oldJwtAlgorithm
            $env:ACCESS_TOKEN_EXPIRE_MINUTES = $oldExpire
            $env:MEDICAL_RECORD_KEY = $oldMedicalKey
            $env:TZ = $oldTz
        }
    }
    finally {
        Pop-Location
    }
}

if (-not $DataOnlyDumpFile) {
    Write-Step "Inserting doctor1 profile and default demo consent"
    # seed_demo_core.sql updates existing rows and inserts only missing rows.
    Invoke-GsqlFile -LocalFile $SeedCoreFile -ContainerFile "/tmp/seed_demo_core.sql"
}
else {
    Write-Output "DataOnlyDumpFile was provided. Demo core seed will be skipped."
}

Write-Step "Current demo data counts"
Invoke-Gsql "SELECT 'users' AS table_name, count(*) AS row_count FROM users UNION ALL SELECT 'patients', count(*) FROM patients UNION ALL SELECT 'medical_records', count(*) FROM medical_records UNION ALL SELECT 'doctors', count(*) FROM doctors UNION ALL SELECT 'consents', count(*) FROM consents UNION ALL SELECT 'access_logs', count(*) FROM access_logs UNION ALL SELECT 'audit_logs', count(*) FROM audit_logs ORDER BY table_name;"

Write-Step "Done"
Write-Output "Container: $TargetContainer"
Write-Output "Database:  $DatabaseName"
Write-Output "Host port: $HostPort"
Write-Output ""
Write-Output "Use this in backend/.env:"
Write-Output "DATABASE_URL=$databaseUrl"
Write-Output "JWT_SECRET=<same value as $EnvPath>"
Write-Output "JWT_ALGORITHM=HS256"
Write-Output "ACCESS_TOKEN_EXPIRE_MINUTES=60"
Write-Output "MEDICAL_RECORD_KEY=<same value as $EnvPath>"
Write-Output "TZ=Asia/Shanghai"
