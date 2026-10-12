param(
    [string]$Image = 'smartwear-judge:1.0.0',
    [string]$HandVideo = '',
    [switch]$RequireBothHands
)

$ErrorActionPreference = 'Stop'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Chưa cài Docker CLI. Xem docs/JUDGE_QUICKSTART.md.'
}

$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$container = "smartwear-verify-$suffix"
$dataVolume = "smartwear-verify-data-$suffix"
$staticVolume = "smartwear-verify-static-$suffix"
$video = Join-Path $env:TEMP "smartwear-verify-$suffix.avi"
$archive = Join-Path $env:TEMP "smartwear-verify-$suffix.zip"
$handSessionId = $null
$created = $false

function Assert-DockerExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step thất bại (Docker exit $LASTEXITCODE)." }
}

try {
    $null = & docker run -d --name $container --pull never --platform linux/amd64 `
        -p '127.0.0.1::8000' `
        -e SMARTWEAR_ENVIRONMENT=development -e SMARTWEAR_JUDGE_MODE=true `
        -e SMARTWEAR_AI_PYTHON=/usr/local/bin/python `
        -e SMARTWEAR_CAPTURE_BACKEND_URL=http://127.0.0.1:8000 `
        -e SMARTWEAR_DATABASE_URL=sqlite:////app/backend/data/smartwear.db `
        -v "${dataVolume}:/app/backend/data" -v "${staticVolume}:/app/backend/static" $Image
    Assert-DockerExit 'Khởi động container thử'
    $created = $true
    $binding = & docker port $container '8000/tcp'
    Assert-DockerExit 'Đọc cổng thử'
    $binding = @($binding)[0]
    if ($binding -notmatch ':(\d+)$') { throw "Không đọc được cổng HTTP: $binding" }
    $baseUrl = "http://127.0.0.1:$($Matches[1])"
    Write-Host "Kiểm thử API và giao diện tại $baseUrl..."

    $ready = $false
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $response = Invoke-RestMethod -Uri "$baseUrl/ready" -TimeoutSec 3
            if ($response.status -eq 'ready') { $ready = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw 'Container không đạt /ready sau 3 phút.' }
    $page = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing -TimeoutSec 10
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch '<html') {
        throw 'Frontend không được phục vụ tại /.'
    }
    $empty = Invoke-RestMethod -Uri "$baseUrl/api/v1/sessions/?limit=1&offset=0" -TimeoutSec 10
    if ($empty.total -ne 0) { throw 'Volume mới không có danh sách phiên trống.' }

    # Synthetic black video only checks the upload pipeline, not hand-recognition accuracy.
    $makeVideo = "import cv2,numpy as np; w=cv2.VideoWriter('/tmp/verify.avi',cv2.VideoWriter_fourcc(*'MJPG'),20,(160,120)); assert w.isOpened(); [w.write(np.zeros((120,160,3),dtype=np.uint8)) for _ in range(20)]; w.release()"
    & docker exec $container python -c $makeVideo
    Assert-DockerExit 'Tạo video thử'
    & docker cp "${container}:/tmp/verify.avi" $video
    Assert-DockerExit 'Lấy video thử'
    $job = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/capture/upload?filename=verify.avi&consent=true" `
        -InFile $video -ContentType 'application/octet-stream' -TimeoutSec 30
    if (-not $job.job_id) { throw 'Upload không trả về job ID.' }
    Write-Host "Đã tải video thử lên; đang chờ AI xử lý (job $($job.job_id))..."

    $result = $null
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Seconds 2
        $result = Invoke-RestMethod -Uri "$baseUrl/api/v1/capture/$($job.job_id)" -TimeoutSec 10
        if ($result.stage -in @('completed', 'failed')) { break }
        if ($i % 15 -eq 14) { Write-Host "  AI: $($result.stage) — $($result.message)" }
    }
    if ($result.stage -ne 'completed' -or -not $result.session_id) {
        throw "Video thử không hoàn tất: $($result.stage) $($result.message)"
    }
    $detail = Invoke-RestMethod -Uri "$baseUrl/api/v1/sessions/$($result.session_id)" -TimeoutSec 10
    if ($detail.action_phases.Count -ne 0 -or $detail.robot_trajectory_points.Count -ne 0) {
        throw 'Video đen sinh hành động hoặc đường đi giả.'
    }
    $sourceUrl = $detail.source_data_url
    if (-not $sourceUrl) { throw 'Phiên không có đường dẫn ZIP nguồn.' }
    Invoke-WebRequest -Uri "$baseUrl$sourceUrl" -OutFile $archive -TimeoutSec 30
    if ((Get-Item $archive).Length -lt 100) { throw 'ZIP nguồn trống.' }
    Write-Host 'Video không có tay, kết quả và ZIP nguồn đã đạt.'

    if ($HandVideo) {
        $handFile = (Resolve-Path -LiteralPath $HandVideo -ErrorAction Stop).Path
        if ((Get-Item -LiteralPath $handFile).Length -gt 50MB) {
            throw 'Video thử tay thật vượt giới hạn upload 50 MiB.'
        }
        $handName = [Uri]::EscapeDataString([IO.Path]::GetFileName($handFile))
        Write-Host "Đang thử video có tay: $handFile"
        $handJob = Invoke-RestMethod -Method Post `
            -Uri "$baseUrl/api/v1/capture/upload?filename=$handName&consent=true" `
            -InFile $handFile -ContentType 'application/octet-stream' -TimeoutSec 30
        if (-not $handJob.job_id) { throw 'Upload video có tay không trả về job ID.' }
        $handResult = $null
        for ($i = 0; $i -lt 120; $i++) {
            Start-Sleep -Seconds 2
            $handResult = Invoke-RestMethod -Uri "$baseUrl/api/v1/capture/$($handJob.job_id)" -TimeoutSec 10
            if ($handResult.stage -in @('completed', 'failed')) { break }
            if ($i % 15 -eq 14) { Write-Host "  Video tay: $($handResult.stage) — $($handResult.message)" }
        }
        if ($handResult.stage -ne 'completed' -or -not $handResult.session_id) {
            throw "Video có tay không hoàn tất: $($handResult.stage) $($handResult.message)"
        }
        $handDetail = Invoke-RestMethod -Uri "$baseUrl/api/v1/sessions/$($handResult.session_id)" -TimeoutSec 10
        if ($handDetail.action_phases.Count -lt 1 -or $handDetail.key_frames.Count -lt 1) {
            throw 'Video có tay không tạo action_phases hoặc keyframes.'
        }
        if ($RequireBothHands) {
            $phases = @($handDetail.action_phases | ForEach-Object { $_.phase })
            if (-not (@($phases | Where-Object { $_ -match '(^|\.)LEFT_' }).Count -gt 0 -and
                       @($phases | Where-Object { $_ -match '(^|\.)RIGHT_' }).Count -gt 0)) {
                throw 'Video hai tay chưa tạo hành động cho cả tay trái và tay phải.'
            }
        }
        if ($handDetail.robot_trajectory_points.Count -ne 0) {
            throw 'Video upload không được tạo đường đi robot giả.'
        }
        $handSessionId = $handResult.session_id
        Write-Host "ĐẠT video có tay: $($handDetail.action_phases.Count) hành động, $($handDetail.key_frames.Count) keyframe ($handSessionId)."
    }
    Write-Host 'Đang thử khởi động lại container...'

    & docker restart $container | Out-Null
    Assert-DockerExit 'Restart container'
    $binding = & docker port $container '8000/tcp'
    Assert-DockerExit 'Đọc cổng sau restart'
    $binding = @($binding)[0]
    if ($binding -notmatch ':(\d+)$') { throw "Không đọc được cổng sau restart: $binding" }
    $baseUrl = "http://127.0.0.1:$($Matches[1])"
    Write-Host "Container đã restart; đang kiểm tra lại tại $baseUrl..."
    $ready = $false
    $lastReadyError = ''
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $readiness = Invoke-RestMethod -Uri "$baseUrl/ready" -TimeoutSec 3
            if ($readiness.status -eq 'ready') {
                $ready = $true; break
            }
            $lastReadyError = "status=$($readiness.status)"
        } catch { $lastReadyError = $_.Exception.Message }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Container không sẵn sàng sau restart tại ${baseUrl}: $lastReadyError" }
    $saved = Invoke-RestMethod -Uri "$baseUrl/api/v1/sessions/$($result.session_id)" -TimeoutSec 10
    if ($saved.session_id -ne $result.session_id) { throw 'Phiên đã lưu bị mất sau restart.' }
    if ($handSessionId) {
        $savedHand = Invoke-RestMethod -Uri "$baseUrl/api/v1/sessions/$handSessionId" -TimeoutSec 10
        if ($savedHand.session_id -ne $handSessionId) { throw 'Phiên video có tay bị mất sau restart.' }
    }
    Write-Host "ĐẠT: giao diện, /ready, volume trống, upload AI thật, ZIP nguồn, lưu qua restart ($($result.session_id))."
} catch {
    if ($created) {
        try { & docker logs --tail 60 $container 2>&1 | Out-Host } catch { }
    }
    throw
} finally {
    if ($created) {
        try { & docker rm -f $container 2>&1 | Out-Null } catch { }
    }
    try { & docker volume rm $dataVolume $staticVolume 2>&1 | Out-Null } catch { }
    Remove-Item -LiteralPath $video, $archive -ErrorAction SilentlyContinue
}
