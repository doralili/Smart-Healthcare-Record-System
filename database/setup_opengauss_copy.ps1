param(
    [string]$TargetContainer = "healthcare-opengauss-dev",
    [string]$SourceContainer = "Healthcare",
    [string]$DatabaseName = "health_security",
    [string]$Image = "opengauss/opengauss:latest",
    [int]$HostPort = 5433,
    [string]$DbSecret = "OpenGauss@123",
    [string]$DumpFilePath = "",
    [switch]$ExportDumpOnly,
    [switch]$NoSourceCopy
)

$ErrorActionPreference = "Stop"

$SchemaFile = Join-Path $PSScriptRoot "schema.sql"
$SeedFile = Join-Path $PSScriptRoot "seed_users.sql"
$DefaultDumpFile = Join-Path $PSScriptRoot "$DatabaseName.copy.sql"
$EffectiveDumpFile = if ($DumpFilePath) {
    $DumpFilePath
}
else {
    $DefaultDumpFile
}
$ContainerDumpFile = "/tmp/$DatabaseName.copy.sql"
$ContainerSchemaFile = "/tmp/schema.sql"
$ContainerSeedFile = "/tmp/seed_users.sql"
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

function ConvertTo-ShellSingleQuoted {
    param([string]$Text)

    return "'" + $Text.Replace("'", "'\''") + "'"
}

function Invoke-OpenGauss {
    param(
        [string]$ContainerName,
        [string]$Command
    )

    $quotedCommand = ConvertTo-ShellSingleQuoted $Command
    & docker exec $ContainerName bash -lc "su - omm -c $quotedCommand"
    if ($LASTEXITCODE -ne 0) {
        throw "openGauss command failed in container '$ContainerName': $Command"
    }
}

function Read-OpenGauss {
    param(
        [string]$ContainerName,
        [string]$Command
    )

    $quotedCommand = ConvertTo-ShellSingleQuoted $Command
    $output = & docker exec $ContainerName bash -lc "su - omm -c $quotedCommand"
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
        try {
            Read-OpenGauss -ContainerName $Name -Command "gsql -d postgres -c `"SELECT 1;`"" *> $null
            Write-Output "openGauss is ready."
            return
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "openGauss did not become ready in time."
}

function Test-DatabaseNameSafety {
    param([string]$Name)

    if ($Name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
        throw "DatabaseName must contain only letters, numbers, and underscores, and cannot start with a number."
    }
}

function Initialize-DatabaseIfMissing {
    param(
        [string]$ContainerName,
        [string]$DbName
    )

    Write-Step "Ensuring database '$DbName' exists"

    $exists = Read-OpenGauss -ContainerName $ContainerName -Command "gsql -d postgres -t -A -c `"SELECT 1 FROM pg_database WHERE datname='$DbName';`""

    if (@($exists) -contains "1") {
        Write-Output "Database '$DbName' already exists."
        return
    }

    Invoke-OpenGauss -ContainerName $ContainerName -Command "gsql -d postgres -c `"CREATE DATABASE $DbName;`""
}

function Test-DatabaseHasPublicTables {
    param(
        [string]$ContainerName,
        [string]$DbName
    )

    $count = Read-OpenGauss -ContainerName $ContainerName -Command "gsql -d $DbName -t -A -c `"SELECT count(*) FROM pg_tables WHERE schemaname='public';`""

    $text = (@($count) | Select-Object -First 1).Trim()
    return [int]$text -gt 0
}

Test-DatabaseNameSafety $DatabaseName

if ($ExportDumpOnly) {
    Write-Step "Exporting database '$DatabaseName' from '$SourceContainer'"

    if (-not (Test-ContainerExists $SourceContainer)) {
        throw "Source container '$SourceContainer' does not exist on this computer."
    }

    if (-not (Test-ContainerRunning $SourceContainer)) {
        Invoke-Docker start $SourceContainer
        Wait-OpenGaussReady $SourceContainer
    }

    $dumpDirectory = Split-Path -Parent $EffectiveDumpFile
    if ($dumpDirectory -and -not (Test-Path $dumpDirectory)) {
        throw "Dump directory does not exist: $dumpDirectory"
    }

    Invoke-OpenGauss -ContainerName $SourceContainer -Command "gs_dump -O -x -f $ContainerDumpFile $DatabaseName"
    Invoke-Docker cp "${SourceContainer}:$ContainerDumpFile" $EffectiveDumpFile

    Write-Step "Dump exported"
    Write-Output "Dump file: $EffectiveDumpFile"
    Write-Output "Share this file with teammates. They can restore it with:"
    Write-Output ".\database\setup_opengauss_copy.ps1 -DumpFilePath `"$EffectiveDumpFile`""
    return
}

Write-Step "Preparing target container '$TargetContainer'"

if (Test-ContainerExists $TargetContainer) {
    if (Test-ContainerRunning $TargetContainer) {
        Write-Output "Target container is already running."
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
Initialize-DatabaseIfMissing -ContainerName $TargetContainer -DbName $DatabaseName

$canRestoreFromDump = $DumpFilePath -and (Test-Path $EffectiveDumpFile)
$canCopyFromSource = -not $NoSourceCopy -and -not $DumpFilePath -and (Test-ContainerExists $SourceContainer)

if ($DumpFilePath -and -not $canRestoreFromDump) {
    throw "Dump file not found: $EffectiveDumpFile"
}

if (Test-DatabaseHasPublicTables -ContainerName $TargetContainer -DbName $DatabaseName) {
    Write-Step "Target database already has tables"
    Write-Output "Skip copy/init to avoid duplicate data."
    Write-Output "Use a new -TargetContainer name if you want a fresh database copy."
}
elseif ($canRestoreFromDump) {
    Write-Step "Restoring database '$DatabaseName' from dump file"

    Invoke-Docker cp $EffectiveDumpFile "${TargetContainer}:$ContainerDumpFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $ContainerDumpFile"
}
elseif ($canCopyFromSource) {
    Write-Step "Copying database '$DatabaseName' from '$SourceContainer' to '$TargetContainer'"

    if (-not (Test-ContainerRunning $SourceContainer)) {
        Invoke-Docker start $SourceContainer
        Wait-OpenGaussReady $SourceContainer
    }

    if (Test-Path $DefaultDumpFile) {
        Remove-Item -LiteralPath $DefaultDumpFile -Force
    }

    Invoke-OpenGauss -ContainerName $SourceContainer -Command "gs_dump -O -x -f $ContainerDumpFile $DatabaseName"
    Invoke-Docker cp "${SourceContainer}:$ContainerDumpFile" $DefaultDumpFile
    Invoke-Docker cp $DefaultDumpFile "${TargetContainer}:$ContainerDumpFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $ContainerDumpFile"

    Remove-Item -LiteralPath $DefaultDumpFile -Force
}
else {
    Write-Step "Initializing '$DatabaseName' from repository SQL files"

    if (-not (Test-Path $SchemaFile)) {
        throw "Schema file not found: $SchemaFile"
    }

    if (-not (Test-Path $SeedFile)) {
        throw "Seed file not found: $SeedFile"
    }

    Invoke-Docker cp $SchemaFile "${TargetContainer}:$ContainerSchemaFile"
    Invoke-Docker cp $SeedFile "${TargetContainer}:$ContainerSeedFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $ContainerSchemaFile"
    Invoke-OpenGauss -ContainerName $TargetContainer -Command "gsql -d $DatabaseName -f $ContainerSeedFile"
}

Write-Step "Done"
Write-Output "Container: $TargetContainer"
Write-Output "Database:  $DatabaseName"
Write-Output "Host port: $HostPort"
Write-Output ""
Write-Output "Use this DATABASE_URL in backend/.env if you use the default script settings:"
$EncodedSecret = [System.Uri]::EscapeDataString($DbSecret)
Write-Output "DATABASE_URL=postgresql+psycopg2://omm:$EncodedSecret@localhost:$HostPort/$DatabaseName"
