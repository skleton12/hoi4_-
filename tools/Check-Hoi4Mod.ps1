<#
    HOI4 모드 로딩 진단 스크립트
    "런처는 모드를 인식하는데 게임에는 전혀 반영되지 않는다" 문제를 찾기 위한 도구.

    사용법 (PowerShell 창에서):
        powershell -ExecutionPolicy Bypass -File .\Check-Hoi4Mod.ps1
        powershell -ExecutionPolicy Bypass -File .\Check-Hoi4Mod.ps1 -ModName "대균열"

    결과 전체를 복사해서 붙여넣으면 원인 분석이 가능하다.
    파일에 저장하려면:
        powershell -ExecutionPolicy Bypass -File .\Check-Hoi4Mod.ps1 | Tee-Object -FilePath report.txt
#>
[CmdletBinding()]
param(
    [string]$ModName = "대균열",
    [int]$ErrorLogLines = 120
)

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$script:FailCount = 0
$script:WarnCount = 0

function Write-Section($title) {
    Write-Host ""
    Write-Host ("=" * 72)
    Write-Host "  $title"
    Write-Host ("=" * 72)
}
function Write-Ok($msg)   { Write-Host "  [ OK ] $msg" }
function Write-Info($msg) { Write-Host "  [    ] $msg" }
function Write-Warn($msg) { $script:WarnCount++; Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { $script:FailCount++; Write-Host "  [FAIL] $msg" -ForegroundColor Red }

function Get-ModField {
    param([string]$Text, [string]$Field)
    $pattern = '(?m)^\s*' + [regex]::Escape($Field) + '\s*=\s*"([^"]*)"'
    if ($Text -match $pattern) { return $Matches[1] }
    return $null
}

# 파일 인코딩 판별: utf8-bom / utf8 / utf16 / non-utf8(대개 CP949 등 ANSI)
function Get-FileEncodingInfo {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $result = [ordered]@{ Encoding = "utf8"; HasBom = $false; Bytes = $bytes.Length }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $result.Encoding = "utf8"; $result.HasBom = $true; return [pscustomobject]$result
    }
    if ($bytes.Length -ge 2 -and (($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) -or ($bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF))) {
        $result.Encoding = "utf16"; $result.HasBom = $true; return [pscustomobject]$result
    }
    try {
        $strict = New-Object System.Text.UTF8Encoding($false, $true)
        [void]$strict.GetString($bytes)
    } catch {
        $result.Encoding = "non-utf8"
    }
    return [pscustomobject]$result
}

function Read-ScriptText {
    param([string]$Path)
    try { return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8) } catch { return "" }
}

# 주석/문자열을 제거한 뒤 중괄호 균형 확인
function Test-BraceBalance {
    param([string]$Text)
    $noComments = [regex]::Replace($Text, '#[^\r\n]*', '')
    $noStrings  = [regex]::Replace($noComments, '"[^"\r\n]*"', '""')
    $open  = ([regex]::Matches($noStrings, '\{')).Count
    $close = ([regex]::Matches($noStrings, '\}')).Count
    return [pscustomobject]@{ Open = $open; Close = $close; Balanced = ($open -eq $close) }
}

function Test-NonAscii {
    param([string]$Text)
    return ($Text -match '[^\x00-\x7F]')
}

Write-Host ""
Write-Host "HOI4 모드 진단 : $ModName"
Write-Host ("생성 시각 : " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))

# ---------------------------------------------------------------------------
Write-Section "1. 사용자 데이터 폴더 (문서\Paradox Interactive\Hearts of Iron IV)"
# ---------------------------------------------------------------------------
$candidates = New-Object System.Collections.Generic.List[string]
$docs = [Environment]::GetFolderPath('MyDocuments')
if ($docs) { $candidates.Add((Join-Path $docs 'Paradox Interactive\Hearts of Iron IV')) }
foreach ($root in @($env:USERPROFILE, $env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial)) {
    if (-not $root) { continue }
    foreach ($d in @('Documents', '문서')) {
        $candidates.Add((Join-Path $root (Join-Path $d 'Paradox Interactive\Hearts of Iron IV')))
    }
}
$userDirs = @($candidates | Where-Object { $_ } | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ })

if ($userDirs.Count -eq 0) {
    Write-Fail "사용자 데이터 폴더를 찾지 못했다. 아래 경로를 직접 확인할 것: %USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV"
} else {
    foreach ($d in $userDirs) { Write-Info "발견: $d" }
    if ($userDirs.Count -gt 1) {
        Write-Warn "사용자 데이터 폴더가 $($userDirs.Count)개 발견됐다. OneDrive 리디렉션 때문에 '런처가 쓰는 폴더'와 '게임이 읽는 폴더'가 갈리는 대표적 상황이다. 어느 쪽 dlc_load.json이 최근에 수정됐는지 아래에서 확인할 것."
    }
}
$primary = $null
foreach ($d in $userDirs) {
    if (Test-Path -LiteralPath (Join-Path $d 'dlc_load.json')) { $primary = $d; break }
}
if (-not $primary -and $userDirs.Count -gt 0) { $primary = $userDirs[0] }
if ($primary) { Write-Ok "기준 폴더로 사용: $primary" }

# ---------------------------------------------------------------------------
Write-Section "2. dlc_load.json (게임이 실제로 켜는 모드 목록)"
# ---------------------------------------------------------------------------
$enabledMods = @()
foreach ($d in $userDirs) {
    $dlcPath = Join-Path $d 'dlc_load.json'
    if (-not (Test-Path -LiteralPath $dlcPath)) { Write-Warn "없음: $dlcPath"; continue }
    $stamp = (Get-Item -LiteralPath $dlcPath).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
    Write-Info "$dlcPath  (최종 수정 $stamp)"
    try {
        $json = Get-Content -LiteralPath $dlcPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $mods = @($json.enabled_mods)
        if ($mods.Count -eq 0) {
            Write-Fail "  enabled_mods 가 비어 있다 -> 게임은 어떤 모드도 로드하지 않는다."
        } else {
            foreach ($m in $mods) { Write-Info "  enabled_mods: $m" }
        }
        if ($d -eq $primary) { $enabledMods = $mods }
    } catch {
        Write-Fail "  파싱 실패: $($_.Exception.Message)"
    }
}
$modEnabled = $false
foreach ($m in $enabledMods) { if ($m -like "*$ModName*") { $modEnabled = $true } }
if ($enabledMods.Count -gt 0) {
    if ($modEnabled) {
        Write-Ok "'$ModName' 가 enabled_mods 에 들어 있다."
    } else {
        Write-Fail "'$ModName' 가 enabled_mods 에 없다. 런처 목록에 보이는 것과 실제 활성화는 별개다. 런처에서 플레이세트를 열어 체크한 뒤 반드시 런처의 [플레이] 버튼으로 실행할 것."
    }
}

# ---------------------------------------------------------------------------
Write-Section "3. mod 폴더 / .mod 디스크립터"
# ---------------------------------------------------------------------------
$modRoot = $null
$modFile = $null
$modDir  = $null
if ($primary) {
    $modRoot = Join-Path $primary 'mod'
    if (Test-Path -LiteralPath $modRoot) {
        Write-Ok "mod 루트: $modRoot"
        $modFiles = @(Get-ChildItem -LiteralPath $modRoot -Filter '*.mod' -File -ErrorAction SilentlyContinue)
        Write-Info ".mod 파일 $($modFiles.Count)개 발견"
        foreach ($f in $modFiles) { Write-Info "  - $($f.Name)" }
        $modFile = $modFiles | Where-Object { $_.BaseName -eq $ModName } | Select-Object -First 1
        if (-not $modFile) { $modFile = $modFiles | Where-Object { $_.Name -like "*$ModName*" } | Select-Object -First 1 }
        if (-not $modFile) {
            Write-Fail "'$ModName.mod' 파일이 mod 폴더에 없다. 모드 폴더와 '나란히' 놓인 .mod 파일이 반드시 필요하다."
        }
    } else {
        Write-Fail "mod 폴더가 없다: $modRoot"
    }
}

$gameVersion = $null
if ($modFile) {
    $text = Read-ScriptText $modFile.FullName
    Write-Ok "디스크립터: $($modFile.FullName)"
    Write-Host "  ---- 내용 ----"
    foreach ($line in ($text -split "`r?`n")) { if ($line.Trim()) { Write-Host "    $line" } }
    Write-Host "  --------------"

    $enc = Get-FileEncodingInfo $modFile.FullName
    if ($enc.Encoding -ne 'utf8') { Write-Fail "  .mod 인코딩이 $($enc.Encoding) 다. UTF-8 이어야 한다." }

    $pName    = Get-ModField $text 'name'
    $pPath    = Get-ModField $text 'path'
    $pVersion = Get-ModField $text 'supported_version'
    $hasArchive = ($text -match '(?m)^\s*archive\s*=')

    if (-not $pName)    { Write-Fail '  name="..." 항목이 없다.' }
    if (-not $pVersion) { Write-Warn '  supported_version="..." 항목이 없다.' }

    if ($hasArchive -and $pPath) {
        Write-Fail "  archive= 와 path= 가 동시에 존재한다. 폴더형 모드는 path= 만 있어야 한다."
    }
    if (-not $pPath -and -not $hasArchive) {
        Write-Fail '  path="mod/폴더명" 항목이 없다. 런처는 목록에 띄우지만 게임은 파일을 못 찾는다.'
    }
    if ($pPath) {
        if ($pPath -match '\\') { Write-Fail "  path 에 역슬래시(\)가 있다: $pPath  -> 슬래시(/)로 바꿀 것." }
        $resolved = $pPath
        if (-not [System.IO.Path]::IsPathRooted($pPath)) { $resolved = Join-Path $primary ($pPath -replace '/', '\') }
        if (Test-Path -LiteralPath $resolved) {
            $modDir = (Get-Item -LiteralPath $resolved).FullName
            Write-Ok "  path 해석 성공 -> $modDir"
        } else {
            Write-Fail "  path 가 가리키는 폴더가 존재하지 않는다 -> $resolved"
        }
    }
    if (Test-NonAscii $modFile.Name) {
        Write-Warn "  .mod 파일명에 한글이 들어 있다: $($modFile.Name)  -> 로딩 실패 시 1순위 용의자. 폴더/파일명을 영문(예: daegyunyeol)으로 바꾸고 path= 도 같이 수정할 것. name= 은 한글로 둬도 된다."
    }
}
if (-not $modDir -and $modRoot) {
    $guess = Join-Path $modRoot $ModName
    if (Test-Path -LiteralPath $guess) { $modDir = $guess; Write-Info "폴더는 존재: $modDir" }
}
if ($modDir) {
    $inner = Join-Path $modDir 'descriptor.mod'
    if (Test-Path -LiteralPath $inner) {
        Write-Ok "모드 폴더 안 descriptor.mod 존재"
        $itext = Read-ScriptText $inner
        $iname = Get-ModField $itext 'name'
        if ($modFile) {
            $oname = Get-ModField (Read-ScriptText $modFile.FullName) 'name'
            if ($iname -ne $oname) { Write-Warn "  descriptor.mod 의 name('$iname') 과 $($modFile.Name) 의 name('$oname') 이 다르다." }
        }
        if ($itext -match '(?m)^\s*path\s*=') { Write-Warn "  폴더 안 descriptor.mod 에는 path= 가 없어도 된다(있어도 무해)." }
    } else {
        Write-Fail "모드 폴더 안에 descriptor.mod 가 없다. mod\$ModName.mod 와 mod\$ModName\descriptor.mod 둘 다 필요하다."
    }
    if (Test-NonAscii (Split-Path $modDir -Leaf)) {
        Write-Warn "모드 폴더명에 한글이 들어 있다. Paradox 런처/게임이 비ASCII 경로에서 문제를 일으킨 사례가 많다."
    }
}

# ---------------------------------------------------------------------------
Write-Section "4. 게임 버전 vs supported_version"
# ---------------------------------------------------------------------------
$gameDirs = @()
foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, 'C:\Program Files (x86)', 'D:\Steam', 'E:\Steam')) {
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
    Write-Ok "게임 설치 폴더: $gameDir"
    $ls = Join-Path $gameDir 'launcher-settings.json'
    if (Test-Path -LiteralPath $ls) {
        try {
            $lj = Get-Content -LiteralPath $ls -Raw -Encoding UTF8 | ConvertFrom-Json
            $gameVersion = $lj.rawVersion
            Write-Ok "게임 버전: $gameVersion"
        } catch { Write-Warn "launcher-settings.json 파싱 실패" }
    }
} else {
    Write-Warn "게임 설치 폴더를 자동으로 찾지 못했다. 버전 비교를 건너뛴다."
}
if ($gameVersion -and $modFile) {
    $sv = Get-ModField (Read-ScriptText $modFile.FullName) 'supported_version'
    if ($sv) {
        $gv = ($gameVersion -split '\.')
        $mv = ($sv -split '\.')
        $mismatch = $false
        for ($i = 0; $i -lt [Math]::Min(2, [Math]::Min($gv.Count, $mv.Count)); $i++) {
            if ($mv[$i] -ne '*' -and $mv[$i] -ne $gv[$i]) { $mismatch = $true }
        }
        if ($mismatch) {
            Write-Fail "supported_version='$sv' 이 게임 버전 '$gameVersion' 과 맞지 않는다. 런처는 모드를 '호환 안 됨'으로 표시하면서 목록에는 계속 보여주고, 플레이세트에서 조용히 빼버린다. supported_version 을 '$($gv[0]).$($gv[1]).*' 로 고칠 것."
        } else {
            Write-Ok "supported_version='$sv' 이 게임 버전 '$gameVersion' 과 호환된다."
        }
    }
}

# ---------------------------------------------------------------------------
Write-Section "5. 모드 파일 구조"
# ---------------------------------------------------------------------------
$focusFiles = @(); $decisionFiles = @(); $categoryFiles = @(); $eventFiles = @(); $ideaFiles = @(); $charFiles = @(); $locFiles = @()
if ($modDir) {
    $all = @(Get-ChildItem -LiteralPath $modDir -Recurse -File -ErrorAction SilentlyContinue)
    Write-Info "총 파일 $($all.Count)개"
    $all | Group-Object { $_.DirectoryName.Substring($modDir.Length).TrimStart('\') } | Sort-Object Name | ForEach-Object {
        $folder = if ($_.Name) { $_.Name } else { '(루트)' }
        Write-Info ("  {0,-50} {1}개" -f $folder, $_.Count)
    }

    function Sub($p) { $x = Join-Path $modDir $p; if (Test-Path -LiteralPath $x) { return @(Get-ChildItem -LiteralPath $x -File -Filter '*.txt' -ErrorAction SilentlyContinue) } return @() }
    $focusFiles    = Sub 'common\national_focus'
    $decisionFiles = Sub 'common\decisions'
    $categoryFiles = Sub 'common\decisions\categories'
    $eventFiles    = Sub 'events'
    $ideaFiles     = Sub 'common\ideas'
    $charFiles     = Sub 'common\characters'

    if ($focusFiles.Count -eq 0)    { Write-Fail "common\national_focus 에 .txt 가 없다. 포커스트리는 반드시 이 경로여야 한다." } else { Write-Ok "common\national_focus : $($focusFiles.Count)개" }
    if ($decisionFiles.Count -eq 0) { Write-Warn "common\decisions 에 .txt 가 없다." } else { Write-Ok "common\decisions : $($decisionFiles.Count)개" }
    if ($categoryFiles.Count -eq 0) { Write-Warn "common\decisions\categories 가 비어 있다. 새 카테고리를 쓰면서 정의하지 않으면 디시전이 화면에 아예 안 뜬다." } else { Write-Ok "common\decisions\categories : $($categoryFiles.Count)개" }
    if ($eventFiles.Count -eq 0)    { Write-Warn "events 폴더에 .txt 가 없다." } else { Write-Ok "events : $($eventFiles.Count)개" }
    if ($ideaFiles.Count -eq 0)     { Write-Warn "common\ideas 에 .txt 가 없다." } else { Write-Ok "common\ideas : $($ideaFiles.Count)개" }
    if ($charFiles.Count -eq 0)     { Write-Warn "common\characters 가 없다. 1.12 이후 어드바이저는 characters 로 정의해야 한다(구형 ideas 전용 어드바이저는 안 뜰 수 있다)." }

    foreach ($bad in @('localization', 'localisation\english\english')) {
        if (Test-Path -LiteralPath (Join-Path $modDir $bad)) { Write-Fail "잘못된 폴더명 발견: $bad" }
    }
    $locDir = Join-Path $modDir 'localisation'
    if (Test-Path -LiteralPath $locDir) {
        $locFiles = @(Get-ChildItem -LiteralPath $locDir -Recurse -File -Filter '*.yml' -ErrorAction SilentlyContinue)
        Write-Ok "localisation : $($locFiles.Count)개 .yml"
    } else {
        Write-Warn "localisation 폴더가 없다(기능은 되지만 이름이 전부 키값으로 보인다)."
    }
}

# ---------------------------------------------------------------------------
Write-Section "6. 인코딩 / 중괄호 / 문법 스모크 테스트"
# ---------------------------------------------------------------------------
if ($modDir) {
    $scripts = @(Get-ChildItem -LiteralPath $modDir -Recurse -File -Filter '*.txt' -ErrorAction SilentlyContinue)
    foreach ($f in $scripts) {
        $rel = $f.FullName.Substring($modDir.Length + 1)
        $enc = Get-FileEncodingInfo $f.FullName
        if ($enc.Encoding -eq 'non-utf8') {
            Write-Fail "$rel : UTF-8 이 아니다(ANSI/CP949 추정). 메모장에서 '다른 이름으로 저장 > 인코딩: UTF-8' 로 다시 저장할 것. 한글이 들어간 파일에서 가장 흔한 파싱 실패 원인이다."
            continue
        }
        if ($enc.Encoding -eq 'utf16') { Write-Fail "$rel : UTF-16 이다. 게임이 못 읽는다."; continue }
        if ($enc.HasBom) { Write-Warn "$rel : UTF-8 BOM 이 붙어 있다. 스크립트 파일은 BOM 없는 UTF-8 을 권장한다." }

        $text = Read-ScriptText $f.FullName
        $b = Test-BraceBalance $text
        if (-not $b.Balanced) { Write-Fail "$rel : 중괄호 불균형 ( { $($b.Open)개 / } $($b.Close)개 )" }
        if ($text -match '[\u2018\u2019\u201C\u201D]') { Write-Fail "$rel : 스마트 따옴표(＂ ＇)가 들어 있다. 워드/한글에서 복사하면 생긴다. 일반 따옴표로 바꿀 것." }
        if ($text -match '[\uFF01-\uFF5E]') { Write-Warn "$rel : 전각 기호(＝ ｛ 등)가 있는지 확인할 것." }
    }
    foreach ($f in $locFiles) {
        $rel = $f.FullName.Substring($modDir.Length + 1)
        $enc = Get-FileEncodingInfo $f.FullName
        if (-not $enc.HasBom -or $enc.Encoding -ne 'utf8') {
            Write-Fail "$rel : 로컬라이제이션 .yml 은 반드시 'UTF-8 BOM 포함' 이어야 한다(현재: $($enc.Encoding), BOM=$($enc.HasBom))."
        }
        $first = (Read-ScriptText $f.FullName) -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1
        if ($first -notmatch '^\uFEFF?\s*l_\w+:') { Write-Fail "$rel : 첫 줄이 'l_english:' 형태가 아니다 (현재: $first)" }
        if ($f.Name -notmatch '_l_\w+\.yml$') { Write-Fail "$rel : 파일명이 '..._l_english.yml' 형식이어야 한다." }
    }
}

# ---------------------------------------------------------------------------
Write-Section "7. 내용 검사 (포커스트리 / 디시전 / 이벤트)"
# ---------------------------------------------------------------------------
foreach ($f in $focusFiles) {
    $t = Read-ScriptText $f.FullName
    $rel = "common\national_focus\$($f.Name)"
    if ($t -notmatch 'focus_tree\s*=\s*\{' -and $t -notmatch 'shared_focus\s*=\s*\{') { Write-Fail "$rel : focus_tree = { 블록이 없다."; continue }
    if ($t -match 'focus_tree\s*=\s*\{') {
        if ($t -notmatch '(?m)^\s*id\s*=') { Write-Fail "$rel : focus_tree 에 id 가 없다." }
        if ($t -notmatch 'country\s*=\s*\{') {
            Write-Fail "$rel : country = { ... } 블록이 없다. 이게 없으면 트리가 어떤 나라에도 배정되지 않아 게임에서 영원히 안 보인다."
        } elseif ($t -notmatch 'tag\s*=\s*KOR') {
            Write-Warn "$rel : country 블록에 tag = KOR 가 안 보인다. 아래 형태여야 한다.`n         country = { factor = 0`n             modifier = { add = 100  tag = KOR }`n         }"
        } else {
            Write-Ok "$rel : focus_tree + country(tag=KOR) 확인"
        }
        if ($t -match '(?m)^\s*default\s*=\s*yes') { Write-Warn "$rel : default = yes 다. 특정 국가 전용 트리라면 default = no 여야 한다." }
    }
    $focusCount = ([regex]::Matches($t, '(?m)^\s*focus\s*=\s*\{')).Count
    Write-Info "$rel : focus $focusCount개"
}

$usedCategories = New-Object System.Collections.Generic.HashSet[string]
foreach ($f in $decisionFiles) {
    $t = Read-ScriptText $f.FullName
    foreach ($m in [regex]::Matches($t, '(?m)^([a-zA-Z_][\w]*)\s*=\s*\{')) { [void]$usedCategories.Add($m.Groups[1].Value) }
    if ($t -match '(?m)^\s*allowed\s*=\s*\{') {
        Write-Info "common\decisions\$($f.Name) : allowed = { } 사용 중 -> 게임 시작 시점에 단 한 번만 평가된다. 여기서 false 면 디시전은 영원히 존재하지 않는다."
    }
}
$definedCategories = New-Object System.Collections.Generic.HashSet[string]
foreach ($f in $categoryFiles) {
    $t = Read-ScriptText $f.FullName
    foreach ($m in [regex]::Matches($t, '(?m)^([a-zA-Z_][\w]*)\s*=\s*\{')) { [void]$definedCategories.Add($m.Groups[1].Value) }
}
if ($usedCategories.Count -gt 0) {
    Write-Info "디시전이 사용하는 카테고리: $($usedCategories -join ', ')"
    Write-Info "모드가 정의한 카테고리  : $(if ($definedCategories.Count) { $definedCategories -join ', ' } else { '(없음)' })"
    foreach ($c in $usedCategories) {
        if (-not $definedCategories.Contains($c)) {
            Write-Warn "카테고리 '$c' 는 이 모드에서 정의되지 않았다. 바닐라 카테고리가 아니라면 디시전 탭에 아무것도 안 뜬다."
        }
    }
}
foreach ($f in $eventFiles) {
    $t = Read-ScriptText $f.FullName
    $rel = "events\$($f.Name)"
    if ($t -notmatch '(?m)^\s*add_namespace\s*=') {
        Write-Fail "$rel : add_namespace 가 없다. 파일 전체가 거부된다."
    } else {
        $ns = @([regex]::Matches($t, '(?m)^\s*add_namespace\s*=\s*(\w+)') | ForEach-Object { $_.Groups[1].Value })
        $ids = @([regex]::Matches($t, '(?m)^\s*id\s*=\s*([\w]+)\.\d+') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
        foreach ($i in $ids) { if ($ns -notcontains $i) { Write-Fail "$rel : id '$i.x' 를 쓰는데 add_namespace = $i 가 선언되지 않았다." } }
        Write-Ok "$rel : namespace $($ns -join ', ') / 이벤트 $(([regex]::Matches($t, '(?m)^\s*(country|news|state|unit_leader|operative_leader)_event\s*=\s*\{')).Count)개"
    }
}

# ---------------------------------------------------------------------------
Write-Section "8. error.log 마지막 $ErrorLogLines 줄"
# ---------------------------------------------------------------------------
if ($primary) {
    $logPath = Join-Path $primary 'logs\error.log'
    if (Test-Path -LiteralPath $logPath) {
        $item = Get-Item -LiteralPath $logPath
        Write-Info "$logPath  (최종 수정 $($item.LastWriteTime), $([math]::Round($item.Length/1KB,1)) KB)"
        Write-Host ""
        Get-Content -LiteralPath $logPath -Tail $ErrorLogLines | ForEach-Object { Write-Host "    $_" }
    } else {
        Write-Warn "error.log 가 없다: $logPath"
    }
    Write-Host ""
    Write-Info "권장 절차: error.log 를 지우고 -> 런처에서 실행 -> 1936 새 게임 시작 -> 게임 종료 -> 이 스크립트 재실행."
}

# ---------------------------------------------------------------------------
Write-Section "요약"
# ---------------------------------------------------------------------------
Write-Host "  FAIL : $script:FailCount"
Write-Host "  WARN : $script:WarnCount"
Write-Host ""
Write-Host "  FAIL 이 하나도 없는데 게임에서 여전히 안 보인다면 다음을 확인할 것:"
Write-Host "   1) 저장된 게임을 불러온 게 아니라 '새 게임(1936)' 으로 시작했는가"
Write-Host "   2) 메인 메뉴 우하단 체크섬이 바닐라와 다른가 (같으면 모드가 로드되지 않은 것)"
Write-Host "   3) KOR 은 1936 년 바닐라에 존재하지 않는 국가다. 일본 디시전으로 해방시킨 뒤에만 트리가 보인다"
Write-Host "   4) 콘솔(~) 에서  tag KOR  로 직접 전환해 트리가 나오는지 확인"
Write-Host ""
