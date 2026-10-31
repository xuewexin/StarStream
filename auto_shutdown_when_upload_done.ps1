# ==============================================================================
# Google Drive 上传完成自动关机监控脚本
# 原理：实时采样网络上传速率，当连续一段时间上传速率低于阈值（说明全部文件已传完），自动执行关机
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Google Drive 上传完成智能自动关机助手"

# 配置参数
$thresholdKB = 150       # 上传速度判断阈值 (低于 150 KB/s 视为空闲)
$idleRequired = 180      # 需连续空闲多少秒才触发关机 (默认 180 秒 / 3 分钟，防止文件交替间隙误关机)
$checkInterval = 3       # 检查间隔时间 (秒)
$idleCount = 0

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       Google Drive 上传完成智能自动关机守护助手                 " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "【监控原理】: 实时监测全机网络上传带宽。"
Write-Host "【空闲判定】: 上传速度低于 $thresholdKB KB/s 视为传输空闲。"
Write-Host "【关机条件】: 连续保持空闲 $idleRequired 秒 (3分钟) 后自动触发关机。"
Write-Host "【安全机制】: 触发关机前会有 60 秒倒计时提醒，按任意键或 Ctrl+C 可取消！"
Write-Host "-----------------------------------------------------------------" -ForegroundColor Gray
Write-Host "正在启动网络适配器采样，请稍候..." -ForegroundColor Green
Start-Sleep -Seconds 2

while ($true) {
    try {
        $samples = (Get-Counter "\Network Interface(*)\Bytes Sent/sec" -ErrorAction SilentlyContinue).CounterSamples
        $totalBytes = ($samples | Measure-Object -Property CookedValue -Sum).Sum
        $speedKB = [math]::Round($totalBytes / 1KB, 1)
        $speedMB = [math]::Round($totalBytes / 1MB, 2)
        $timeStr = Get-Date -Format "HH:mm:ss"

        if ($speedKB -ge $thresholdKB) {
            # 正在高速上传中
            if ($idleCount -gt 0) {
                $msg = "[{0}] 上传流量恢复 ({1} MB/s)，重置空闲计时！" -f $timeStr, $speedMB
                Write-Host $msg -ForegroundColor Green
            }
            $idleCount = 0
            $msg = "[{0}] 正在高速上传中: {1} MB/s ({2} KB/s) | 传输进行中，保持开机..." -f $timeStr, $speedMB, $speedKB
            Write-Host $msg -ForegroundColor White
        } else {
            # 速度低于阈值，可能已传完
            $idleCount += $checkInterval
            $remain = $idleRequired - $idleCount
            if ($remain -lt 0) { $remain = 0 }
            $msg = "[{0}] 上传速度低 ({1} KB/s < {2} KB/s) | 已空闲: {3}/{4} 秒 (剩余 {5} 秒关机)" -f $timeStr, $speedKB, $thresholdKB, $idleCount, $idleRequired, $remain
            Write-Host $msg -ForegroundColor Yellow

            if ($idleCount -ge $idleRequired) {
                Write-Host ""
                Write-Host "=================================================================" -ForegroundColor Red
                Write-Host "检测到所有文件已上传完毕！网络传输已连续 3 分钟保持空闲状态！" -ForegroundColor Red
                Write-Host "电脑将在 60 秒后自动关机！如果想取消，请关闭本窗口或按任意键！" -ForegroundColor Yellow
                Write-Host "=================================================================" -ForegroundColor Red

                # 调用 Windows 关机指令，预留 60 秒缓冲
                shutdown.exe -s -t 60 -c "Google Drive 全部文件已上传完成，电脑即将安全关机！"

                Write-Host "提示：如需取消本次关机，可在键盘上按任意键 (或执行 shutdown -a)..." -ForegroundColor Cyan
                $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
                shutdown.exe -a
                Write-Host "已成功取消关机！脚本将退出。" -ForegroundColor Green
                Start-Sleep -Seconds 3
                break
            }
        }
    } catch {
        Write-Host "网络采样异常，正在重试: $_" -ForegroundColor DarkGray
    }

    Start-Sleep -Seconds $checkInterval
}
