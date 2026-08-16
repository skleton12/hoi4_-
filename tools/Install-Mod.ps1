<#
    대균열 모드 설치 스크립트

    저장소의 mod\daegyunyeol 을 HOI4 모드 폴더로 통째로 복사한다(덮어쓰기).
    설치된 게임 버전을 읽어 supported_version 을 자동으로 맞춰준다.

    사용법 (저장소 폴더에서):
        powershell -ExecutionPolicy Bypass -File .\tools\Install-Mod.ps1

    런처 플레이세트에 자동 등록까지 하려면:
        powershell -ExecutionPolicy Bypass -File .\tools\Install-Mod.ps1 -Enable

    한글 이름의 예전 모드를 같이 지우려면:
        powershell -ExecutionPolicy Bypass -File .\tools\Install-Mod.ps1 -RemoveOld "대균열"
#>
[CmdletBinding()]
param(
    [string]$Source,
    [switch]$Enable,
    [string]$RemoveOld,
    [switch]$NoMarker
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ModFolderName = "daegyunyeol"

function Info($m) { Write-Host "  [    ] $m" }
function Ok($m)   { Write-Host "  [ OK ] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }

# --- 소스 확인 ---------------------------------------------------------------
if (-not $Source) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $Source = Join-Path $repoRoot "mod\$ModFolderName"
}
if (-not (Test-Path -LiteralPath $Source)) { throw "소스 폴더를 찾을 수 없다: $Source" }
$Source = (Get-Item -LiteralPath $Source).FullName
$SourceModFile = Join-Path (Split-Path -Parent $Source) "$ModFolderName.mod"
if (-not (Test-Path -LiteralPath $SourceModFile)) { throw "$ModFolderName.mod 을 찾을 수 없다: $SourceModFile" }
Ok "소스: $Source"

# --- HOI4 사용자 폴더 찾기 ---------------------------------------------------
$candidates = New-Object System.Collections.Generic.List[string]
$docs = [Environment]::GetFolderPath('MyDocuments')
if ($docs) { $candidates.Add((Join-Path $docs 'Paradox Interactive\Hearts of Iron IV')) }
foreach ($root in @($env:USERPROFILE, $env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial)) {
    if (-not $root) { continue }
    foreach ($d in @('Documents', '문서')) {
        $candidates.Add((Join-Path $root (Join-Path $d 'Paradox Interactive\Hearts of Iron IV')))
    }
}
$userDirs = @($candidates | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ })
if ($userDirs.Count -eq 0) { throw "HOI4 사용자 데이터 폴더를 찾을 수 없다. 게임을 한 번 실행한 뒤 다시 시도할 것." }

$userDir = $userDirs | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'dlc_load.json') } | Select-Object -First 1
if (-not $userDir) { $userDir = $userDirs[0] }
if ($userDirs.Count -gt 1) {
    Warn "사용자 폴더가 여러 개 발견됐다(OneDrive 리디렉션). 설치 대상은 dlc_load.json 이 있는 쪽으로 정했다."
    foreach ($d in $userDirs) { Info "  후보: $d" }
}
Ok "설치 대상: $userDir"

# --- 게임 버전으로 supported_version 맞추기 ----------------------------------
$gameVersion = $null
$gameDirs = @()
foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, 'D:\Steam', 'E:\Steam')) {
    if (-not $base) { continue }
    $gameDirs += (Join-Path $base 'Steam\steamapps\common\Hearts of Iron IV')
    $gameDirs += (Join-Path $base 'steamapps\common\Hearts of Iron IV')
}
$steamRoot = ${env:ProgramFiles(x86)}
if ($steamRoot) {
    $vdf = Join-Path $steamRoot 'Steam\steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s*"([^"]+)"')) {
            $gameDirs += (Join-Path ($m.Groups[1].Value -replace '\\\\', '\') 'steamapps\common\Hearts of Iron IV')
        }
    }
}
$gameDir = $gameDirs | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($gameDir) {
    $ls = Join-Path $gameDir 'launcher-settings.json'
    if (Test-Path -LiteralPath $ls) {
        try { $gameVersion = (Get-Content -LiteralPath $ls -Raw -Encoding UTF8 | ConvertFrom-Json).rawVersion } catch { }
    }
}
$supported = $null
if ($gameVersion) {
    $p = $gameVersion -split '\.'
    $supported = "$($p[0]).$($p[1]).*"
    Ok "게임 버전 $gameVersion 감지 -> supported_version=`"$supported`""
} else {
    Warn "게임 버전을 감지하지 못했다. .mod 파일의 supported_version 을 직접 확인할 것."
}

# --- 복사 --------------------------------------------------------------------
$modRoot = Join-Path $userDir 'mod'
if (-not (Test-Path -LiteralPath $modRoot)) { New-Item -ItemType Directory -Path $modRoot -Force | Out-Null }
$target = Join-Path $modRoot $ModFolderName

if (Test-Path -LiteralPath $target) {
    Info "기존 폴더 삭제: $target"
    Remove-Item -LiteralPath $target -Recurse -Force
}
Copy-Item -LiteralPath $Source -Destination $target -Recurse -Force
Ok "복사 완료: $target"

# 로딩 확인용 마커. 일본 국가명을 'Japan [DAEGYUNYEOL OK]' 로 바꾼다.
$marker = Join-Path $target 'localisation\replace\daegyunyeol_marker_l_english.yml'
if ($NoMarker) {
    if (Test-Path -LiteralPath $marker) {
        Remove-Item -LiteralPath $marker -Force
        Ok "로딩 마커 제외 (-NoMarker)"
    }
} elseif (Test-Path -LiteralPath $marker) {
    Info "로딩 마커 포함. 국가 선택 화면의 일본 이름으로 로드 여부를 판정할 수 있다."
    Info "  빼려면 -NoMarker 를 붙여 다시 실행할 것."
}

# .mod 두 개(폴더 옆 + 폴더 안)를 모두 쓴다. 폴더형 모드는 둘 다 필요하다.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$modText = [System.IO.File]::ReadAllText($SourceModFile, [System.Text.Encoding]::UTF8)
if ($supported) { $modText = [regex]::Replace($modText, '(?m)^\s*supported_version\s*=\s*"[^"]*"', "supported_version=`"$supported`"") }

$outerPath = Join-Path $modRoot "$ModFolderName.mod"
[System.IO.File]::WriteAllText($outerPath, $modText, $utf8NoBom)
Ok "작성: $outerPath"

$innerText = [regex]::Replace($modText, '(?m)^\s*path\s*=\s*"[^"]*"\r?\n', '')
$innerPath = Join-Path $target 'descriptor.mod'
[System.IO.File]::WriteAllText($innerPath, $innerText, $utf8NoBom)
Ok "작성: $innerPath"

# --- 예전 한글 모드 정리 (요청 시에만) ---------------------------------------
if ($RemoveOld) {
    $oldDir  = Join-Path $modRoot $RemoveOld
    $oldFile = Join-Path $modRoot "$RemoveOld.mod"
    foreach ($p in @($oldDir, $oldFile)) {
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force; Ok "삭제: $p" }
    }
}

# --- 플레이세트 등록 ---------------------------------------------------------
$dlc = Join-Path $userDir 'dlc_load.json'
$entry = "mod/$ModFolderName.mod"
if (Test-Path -LiteralPath $dlc) {
    $json = Get-Content -LiteralPath $dlc -Raw -Encoding UTF8 | ConvertFrom-Json
    $mods = @($json.enabled_mods)
    if ($mods -contains $entry) {
        Ok "이미 활성화되어 있다: $entry"
    } elseif ($Enable) {
        Copy-Item -LiteralPath $dlc -Destination "$dlc.bak" -Force
        $json.enabled_mods = @($mods + $entry)
        ($json | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $dlc -Encoding UTF8
        Ok "dlc_load.json 에 추가했다 (백업: $dlc.bak)"
        Warn "런처를 열면 플레이세트가 이 값을 덮어쓸 수 있다. 런처에서도 체크되어 있는지 확인할 것."
    } else {
        Warn "dlc_load.json 에 '$entry' 가 없다. 런처에서 모드를 켜거나 -Enable 옵션으로 다시 실행할 것."
        Info "현재 활성화된 모드: $(if ($mods.Count) { $mods -join ', ' } else { '(없음)' })"
    }
} else {
    Warn "dlc_load.json 이 없다: $dlc"
}

Write-Host ""
Ok "설치 완료."
Write-Host ""
Write-Host "  다음 순서로 확인할 것:"
Write-Host "   1) logs\error.log 를 삭제"
Write-Host "   2) 런처에서 '대균열' 체크 -> [플레이]"
Write-Host "   3) 1936 새 게임, 일본 선택"
Write-Host "   4) 디시전 탭 -> '대균열' 카테고리 -> '대균열 발동'"
Write-Host "   5) 콘솔(~) 에서  tag KOR  -> 포커스트리 확인"
Write-Host "   6) 안 되면  tools\Check-Hoi4Mod.ps1 -ModName daegyunyeol  실행 후 출력 전달"
Write-Host ""
