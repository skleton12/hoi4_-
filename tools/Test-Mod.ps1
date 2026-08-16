<#
    대균열 테스트 한 방 스크립트.

    1단계 — 설치하고 로그를 비운다:
        powershell -ExecutionPolicy Bypass -File .\tools\Test-Mod.ps1

       게임을 켜서 확인한 뒤 종료한다.

    2단계 — 결과를 파일 하나로 모은다:
        powershell -ExecutionPolicy Bypass -File .\tools\Test-Mod.ps1 -Collect

       daegyunyeol-report.txt 가 만들어진다. 그 내용을 그대로 붙여넣으면 된다.
#>
[CmdletBinding()]
param(
    [switch]$Collect,
    [string]$ModName = "daegyunyeol"
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$repoRoot = Split-Path -Parent $PSScriptRoot
$install  = Join-Path $PSScriptRoot "Install-Mod.ps1"
$check    = Join-Path $PSScriptRoot "Check-Hoi4Mod.ps1"
$report   = Join-Path $repoRoot "daegyunyeol-report.txt"

# --- HOI4 사용자 폴더 ---------------------------------------------------------
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
$userDir = $userDirs | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'dlc_load.json') } | Select-Object -First 1
if (-not $userDir -and $userDirs.Count) { $userDir = $userDirs[0] }

if ($Collect) {
    # ---------------------------------------------------------------------
    Write-Host ""
    Write-Host "결과를 모으는 중..."
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("=== 대균열 테스트 결과 ===")
    $lines.Add("생성 시각: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
    $lines.Add("")

    $lines.Add("=== 진단 스크립트 ===")
    $out = & powershell -ExecutionPolicy Bypass -File $check -ModName $ModName 2>&1 | Out-String
    $lines.Add($out)

    $lines.Add("=== error.log ===")
    if ($userDir) {
        $log = Join-Path $userDir 'logs\error.log'
        if (Test-Path -LiteralPath $log) {
            $item = Get-Item -LiteralPath $log
            $lines.Add("$log  ($([math]::Round($item.Length/1KB,1)) KB, 최종 수정 $($item.LastWriteTime))")
            $lines.Add("")
            $lines.AddRange([string[]](Get-Content -LiteralPath $log -Tail 400))
        } else {
            $lines.Add("error.log 가 없다: $log")
            $lines.Add("게임이 실행되지 않았거나, 오류가 하나도 없었다는 뜻이다.")
        }

        $lines.Add("")
        $lines.Add("=== game.log 마지막 60줄 ===")
        $glog = Join-Path $userDir 'logs\game.log'
        if (Test-Path -LiteralPath $glog) {
            $lines.AddRange([string[]](Get-Content -LiteralPath $glog -Tail 60))
        } else {
            $lines.Add("game.log 가 없다: $glog")
        }
    } else {
        $lines.Add("HOI4 사용자 폴더를 찾지 못했다.")
    }

    Set-Content -LiteralPath $report -Value $lines -Encoding UTF8
    Write-Host ""
    Write-Host "  저장 완료: $report" -ForegroundColor Green
    Write-Host "  이 파일 내용을 그대로 붙여넣으면 된다."
    Write-Host ""
    exit 0
}

# --- 1단계 -------------------------------------------------------------------
Write-Host ""
Write-Host "==================== 1단계: 설치 ====================" -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File $install -Enable

if ($userDir) {
    $logDir = Join-Path $userDir 'logs'
    foreach ($f in @('error.log', 'game.log')) {
        $p = Join-Path $logDir $f
        if (Test-Path -LiteralPath $p) {
            Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
            Write-Host "  로그 삭제: $p"
        }
    }
}

Write-Host ""
Write-Host "==================== 2단계: 게임에서 확인 ====================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  A. 런처를 열고 '대균열' 이 체크되어 있는지 확인 -> [플레이]"
Write-Host "     (스팀에서 바로 실행하지 말고 반드시 런처의 플레이 버튼)"
Write-Host ""
Write-Host "  B. 국가 선택 화면에서 일본 이름을 본다. 이게 핵심 판정이다:"
Write-Host ""
Write-Host "       'Japan [DAEGYUNYEOL OK]'  ->  모드가 로드되고 있다" -ForegroundColor Green
Write-Host "       'Japan' 또는 '일본'        ->  모드가 전혀 로드되지 않았다" -ForegroundColor Red
Write-Host ""
Write-Host "     이 글자는 일부러 영문이라 한글 폰트가 없어도 무조건 보인다."
Write-Host ""
Write-Host "  C. 로드되고 있다면: 1936 새 게임 -> 일본 -> 디시전 탭 -> '대균열' 카테고리"
Write-Host "     로드가 안 된다면: 여기서 멈추고 바로 3단계로 간다."
Write-Host ""
Write-Host "  D. 게임을 종료한다."
Write-Host ""
Write-Host "==================== 3단계: 결과 수집 ====================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  powershell -ExecutionPolicy Bypass -File .\tools\Test-Mod.ps1 -Collect"
Write-Host ""
