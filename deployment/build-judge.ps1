param(
    [switch]$SkipExport
)

$ErrorActionPreference = 'Stop'
# A CMD window opened before Docker Desktop was installed keeps an old PATH.
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [Environment]::GetEnvironmentVariable('Path', 'User')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$image = 'smartwear-judge:1.0.0'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Chưa cài Docker. Xem docs/JUDGE_QUICKSTART.md để cài WSL 2 và Docker Desktop.'
}
$engine = & docker info --format '{{.OSType}}' 2>&1
if ($LASTEXITCODE -ne 0 -or $engine -ne 'linux') {
    throw 'Hãy mở Docker Desktop, chuyển sang Linux containers, rồi chạy lại.'
}

Push-Location $root
try {
    & docker build --platform linux/amd64 --file Dockerfile.judge --tag $image .
    if ($LASTEXITCODE -ne 0) { throw 'Build Docker thất bại. Chưa xuất gói.' }
    & (Join-Path $PSScriptRoot 'verify-judge.ps1') -Image $image
    if ($LASTEXITCODE -ne 0) { throw 'Kiểm thử Docker thất bại. Chưa xuất gói.' }
    if ($SkipExport) { Write-Host 'Image đã build và đạt kiểm tra; bỏ qua xuất TAR.'; return }

    $release = Join-Path $root 'release/SmartWear-Judge-1.0.0'
    New-Item -ItemType Directory -Path $release -Force | Out-Null
    & docker image save --output (Join-Path $release 'smartwear-judge.tar') $image
    if ($LASTEXITCODE -ne 0) { throw 'Không xuất được image TAR.' }
    Copy-Item (Join-Path $root 'compose.judge.yaml') (Join-Path $release 'compose.judge.yaml')
    Copy-Item (Join-Path $root 'docs/JUDGE_QUICKSTART.md') (Join-Path $release 'JUDGE_QUICKSTART.md')
    Copy-Item (Join-Path $root 'deployment/THIRD_PARTY_NOTICES.md') (Join-Path $release 'THIRD_PARTY_NOTICES.md')

    $head = (& git rev-parse HEAD).Trim()
    $dirty = [bool]((& git status --porcelain=v1 --untracked-files=no) | Select-Object -First 1)
    $imageId = (& docker image inspect --format '{{.Id}}' $image).Trim()
    # Hash the application files inside the built image. This identifies the
    # actual snapshot even when the local Git worktree has uncommitted changes.
    $snapshotCode = "import hashlib,pathlib; root=pathlib.Path('/app'); h=hashlib.sha256(); files=sorted(p for name in ('backend','ai','frontend/dist') for p in (root/name).rglob('*') if p.is_file()); [(h.update(str(p.relative_to(root)).encode('utf-8')),h.update(p.read_bytes())) for p in files]; print(h.hexdigest())"
    $snapshot = (& docker run --rm --pull never --entrypoint python $image -c $snapshotCode).Trim()
    if ($LASTEXITCODE -ne 0 -or $snapshot -notmatch '^[0-9a-f]{64}$') {
        throw 'Không tính được checksum của mã thực tế trong image.'
    }
    $manifest = [ordered]@{
        version = '1.0.0'
        image = $image
        platform = 'linux/amd64'
        image_id = $imageId
        git_head = $head
        tracked_worktree_dirty = $dirty
        application_snapshot_sha256 = $snapshot
        model_sha256 = (Get-FileHash (Join-Path $root 'ai/hand_landmarker.task') -Algorithm SHA256).Hash.ToLowerInvariant()
        verified_at_utc = [DateTime]::UtcNow.ToString('o')
        verification = 'isolated fresh-volume HTTP upload + restart passed'
        licensing = 'Review THIRD_PARTY_NOTICES.md and model redistribution rights before external handoff'
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $release 'manifest.json'),
        (($manifest | ConvertTo-Json -Depth 5) + "`n"), $utf8)
    $files = 'smartwear-judge.tar','compose.judge.yaml','JUDGE_QUICKSTART.md','THIRD_PARTY_NOTICES.md','manifest.json'
    $hashes = foreach ($file in $files) {
        $hash = (Get-FileHash (Join-Path $release $file) -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $file"
    }
    [System.IO.File]::WriteAllText((Join-Path $release 'SHA256SUMS.txt'),
        (($hashes -join "`n") + "`n"), $utf8)
    Write-Host "Đã tạo gói Docker: $release"
} finally {
    Pop-Location
}
