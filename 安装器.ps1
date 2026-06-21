# Claude Code 扩展汉化 · Windows GUI 安装器
# ============================================
# 双击安装器.bat 启动,本脚本画一个窗口、跑一键汉化.py、实时显示进度。
# 关闭窗口不会终止后台 Python 进程。

param(
    [switch]$Uninstall  # 加 -Uninstall 时切换到卸载模式(预留,先空跑)
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script:python = "python"
$script:mainScript = Join-Path $script:here "一键汉化.py"

# ---- 窗口 ----
$form = New-Object System.Windows.Forms.Form
$form.Text = "Claude Code 扩展汉化 · 安装器"
$form.Size = New-Object System.Drawing.Size(720, 540)
$form.StartPosition = "CenterScreen"
$form.MinimumSize = New-Object System.Drawing.Size(640, 480)
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

# 标题
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "Claude Code 扩展汉化工具"
$lblTitle.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 14, [System.Drawing.FontStyle]::Bold)
$lblTitle.Location = New-Object System.Drawing.Point(20, 16)
$lblTitle.Size = New-Object System.Drawing.Size(680, 32)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text = "一键完成扩展界面 + CLI spinner 汉化。窗口可关闭,后台 Python 进程会继续跑到结束。"
$lblSub.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
$lblSub.Location = New-Object System.Drawing.Point(20, 50)
$lblSub.Size = New-Object System.Drawing.Size(680, 24)
$lblSub.ForeColor = [System.Drawing.Color]::FromArgb(71, 85, 105)
$form.Controls.Add($lblSub)

# 步骤指示
$lblStep = New-Object System.Windows.Forms.Label
$lblStep.Text = "状态：就绪"
$lblStep.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10, [System.Drawing.FontStyle]::Bold)
$lblStep.Location = New-Object System.Drawing.Point(20, 90)
$lblStep.Size = New-Object System.Drawing.Size(680, 24)
$form.Controls.Add($lblStep)

# 进度条
$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Location = New-Object System.Drawing.Point(20, 120)
$progress.Size = New-Object System.Drawing.Size(680, 22)
$progress.Minimum = 0
$progress.Maximum = 100
$progress.Value = 0
$form.Controls.Add($progress)

# 日志框
$log = New-Object System.Windows.Forms.RichTextBox
$log.Location = New-Object System.Drawing.Point(20, 152)
$log.Size = New-Object System.Drawing.Size(680, 300)
$log.ReadOnly = $true
$log.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$log.ForeColor = [System.Drawing.Color]::FromArgb(226, 232, 240)
$log.Font = New-Object System.Drawing.Font("Consolas", 9)
$form.Controls.Add($log)

# 按钮区
$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "开始汉化"
$btnStart.Location = New-Object System.Drawing.Point(20, 470)
$btnStart.Size = New-Object System.Drawing.Size(140, 36)
$btnStart.BackColor = [System.Drawing.Color]::FromArgb(37, 99, 235)
$btnStart.ForeColor = [System.Drawing.Color]::White
$btnStart.FlatStyle = "Flat"
$btnStart.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($btnStart)

$btnReadme = New-Object System.Windows.Forms.Button
$btnReadme.Text = "打开 README"
$btnReadme.Location = New-Object System.Drawing.Point(170, 470)
$btnReadme.Size = New-Object System.Drawing.Size(140, 36)
$btnReadme.FlatStyle = "Flat"
$form.Controls.Add($btnReadme)

$btnClose = New-Object System.Windows.Forms.Button
$btnClose.Text = "关闭"
$btnClose.Location = New-Object System.Drawing.Point(560, 470)
$btnClose.Size = New-Object System.Drawing.Size(140, 36)
$btnClose.FlatStyle = "Flat"
$form.Controls.Add($btnClose)

# ---- 日志工具 ----
$script:logBuf = ""
function Append-Log {
    param([string]$Text, [string]$Color = "default")
    $stamp = (Get-Date).ToString("HH:mm:ss")
    $prefix = "[$stamp] "
    $script:logBuf += $prefix + $Text + "`r`n"
    # 限制行数,避免卡顿
    $lines = $script:logBuf -split "`r`n"
    if ($lines.Count -gt 500) {
        $script:logBuf = ($lines[-500..-1] -join "`r`n")
    }
    $log.Text = $script:logBuf
    $log.SelectionStart = $log.Text.Length
    $log.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Set-Step {
    param([string]$Text, [int]$Percent)
    $lblStep.Text = "状态：" + $Text
    $progress.Value = [Math]::Min(100, [Math]::Max(0, $Percent))
    [System.Windows.Forms.Application]::DoEvents()
}

# ---- 跑 Python 子进程,实时回灌日志 ----
function Run-Python {
    param([string[]]$Args)

    Set-Step "正在运行 Python..." 5
    Append-Log ">>> python 一键汉化.py $($Args -join ' ')"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $script:python
    $psi.Arguments = "`"$script:mainScript`" " + ($Args -join ' ')
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    try {
        $p = [System.Diagnostics.Process]::Start($psi)
    } catch {
        Append-Log "❌ 启动 Python 失败：$_" "err"
        return $false
    }

    # 异步读 stdout/stderr
    $p.add_OutputDataReceived({
        param($s, $e)
        if ($e.Data) { Append-Log $e.Data }
    })
    $p.add_ErrorDataReceived({
        param($s, $e)
        if ($e.Data) { Append-Log $e.Data "err" }
    })
    $p.BeginOutputReadLine()
    $p.BeginErrorReadLine()

    # 等结束,期间持续 pump 消息
    while (-not $p.HasExited) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 100
    }
    $p.WaitForExit()
    Set-Step "Python 进程结束(退出码 $($p.ExitCode))" 95
    return ($p.ExitCode -eq 0)
}

# ---- 按钮事件 ----
$btnStart.Add_Click({
    if (-not (Test-Path $script:mainScript)) {
        [System.Windows.Forms.MessageBox]::Show("找不到 一键汉化.py,确认本 .ps1 跟它在同一目录。", "错误", "OK", "Error")
        return
    }
    $btnStart.Enabled = $false
    $btnReadme.Enabled = $false

    $ok = Run-Python @("--audit")

    if ($ok) {
        Set-Step "✅ 完成！请到 Cursor/VSCode 里按 Ctrl+Shift+P → Developer: Reload Window" 100
        Append-Log ""
        Append-Log "🎉 汉化已完成。下一步：到 Cursor/VSCode 里 Ctrl+Shift+P → Developer: Reload Window 生效。"
    } else {
        Set-Step "❌ 失败,看上方日志" 100
        Append-Log "❌ 进程非零退出,看上面 Python 输出排查。"
    }

    $btnStart.Enabled = $true
    $btnReadme.Enabled = $true
})

$btnReadme.Add_Click({
    $readme = Join-Path $script:here "README.md"
    if (Test-Path $readme) {
        Start-Process $readme
    } else {
        [System.Windows.Forms.MessageBox]::Show("README.md 不存在", "提示", "OK", "Information")
    }
})

$btnClose.Add_Click({ $form.Close() })

# ---- 启动 ----
Append-Log "就绪。按 [开始汉化] 启动。"
Append-Log "本工具会:"
Append-Log "  1) 定位 Cursor/VSCode 里的 Claude Code 扩展"
Append-Log "  2) 备份原版 index.js"
Append-Log "  3) 应用扩展 UI 汉化(300+ 条字符串)"
Append-Log "  4) 注入 CLI spinner 汉化(187 动词 + 41 提示)"
Append-Log "  5) 语法校验 + 覆盖率审计"
Append-Log ""
Append-Log "提示：卸载请跑 node apply-spinner.cjs --remove 还原 settings.json"

[System.Windows.Forms.Application]::Run($form)
