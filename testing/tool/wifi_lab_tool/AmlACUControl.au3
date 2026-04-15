; 设置AutoIt脚本编码为UTF-8带BOM格式，确保中文正常显示
#Region ;**** 脚本元信息 ****
#AutoIt3Wrapper_Icon=
#AutoIt3Wrapper_Outfile=ACUController.exe
#AutoIt3Wrapper_Compression=4       ; 压缩等级
#AutoIt3Wrapper_UseUpx=y           ; 使用UPX压缩
#AutoIt3Wrapper_UseAnsi=n          ; 禁用ANSI编码，防止中文乱码
#EndRegion ;**** 脚本元信息 ****

#include <MsgBoxConstants.au3>

; ---------- 全局设置 ----------
Opt("WinTitleMatchMode", 2) ; 允许窗口标题部分匹配，防止版本尾巴不同导致找不到窗体

; 常量定义
Global Const $TARGET_EXE   = "ACUControlTool.exe"  ; 目标程序文件名
Global Const $TARGET_TITLE = "AcuControlTool"      ; 目标窗口标题（可部分匹配）

; ============= 通用置顶/前置辅助 =============
; 让窗口 显示+还原+激活+置顶（TopMost）
Func _BringWindowTopMost($vWin)
    Local $hWnd = 0
    If IsHWnd($vWin) Then
        $hWnd = $vWin
    Else
        $hWnd = WinGetHandle($vWin)
    EndIf
    If $hWnd = 0 Then Return 0

    ; 显示并还原
    WinSetState($hWnd, "", @SW_SHOW)
    WinSetState($hWnd, "", @SW_RESTORE)

    ; 激活并置顶
    WinActivate($hWnd)
    WinSetOnTop($hWnd, "", 1)

    ; 等待活跃
    WinWaitActive($hWnd, "", 2)
    Sleep(120)
    Return $hWnd
EndFunc

; 取消 TopMost（可选）
Func _CancelTopMost($vWin)
    Local $hWnd = 0
    If IsHWnd($vWin) Then
        $hWnd = $vWin
    Else
        $hWnd = WinGetHandle($vWin)
    EndIf
    If $hWnd <> 0 Then WinSetOnTop($hWnd, "", 0)
EndFunc

; ============= 基础工具函数 =============
; 显示错误信息（统一处理编码问题）
Func ShowError($title, $message)
    MsgBox(16, $title, $message, 2)
EndFunc

; 等待控件出现，超时自动报错并退出（返回控件句柄）
Func WaitForControlEx($sTitle, $sControlID, $iTimeout = 10, $bExitOnFail = True)
    Local $hControl = 0
    Local $t0 = TimerInit()
    While TimerDiff($t0) < $iTimeout * 1000
        $hControl = ControlGetHandle($sTitle, "", $sControlID)
        If $hControl <> 0 Then Return $hControl
        Sleep(120)
    WEnd

    If $bExitOnFail Then
        MsgBox(16, "错误", "控件 [" & $sControlID & "] 未在 " & $iTimeout & " 秒内出现！")
        Exit
    EndIf
    Return 0
EndFunc

; ============= 目标程序处理 =============
; 启动/附着到 ACUControlTool 程序，并确保窗口置顶到最前。返回窗口句柄。
Func HandleACUControlTool()
    Local $hWnd = 0

    If ProcessExists($TARGET_EXE) Then
        ; 程序已在运行，尝试找到窗口
        $hWnd = WinGetHandle($TARGET_TITLE)
        If $hWnd = 0 Then
            ; 可能启动了但窗体尚未就绪，等待一下
            $hWnd = WinWait($TARGET_TITLE, "", 5)
        EndIf

        If $hWnd <> 0 Then
            _BringWindowTopMost($hWnd)
            ; 提示（短提示，避免打断）
            MsgBox(0, "提示", "程序已在运行，已激活并置顶。", 1)
            Return $hWnd
        Else
            ; 找不到窗体但进程在，继续运行一次以促使窗体出现（部分程序允许多实例，也可换成 ShellExecute 或发送消息）
            MsgBox(48, "注意", "检测到进程存在，但未找到窗口。尝试重新启动以拉起窗口。", 1)
        EndIf
    EndIf

    ; 程序未运行或窗口未找到 -> 启动
    MsgBox(0, "启动", "启动程序: " & $TARGET_EXE & @CRLF, 1)
    Local $iPID = Run($TARGET_EXE)
    If @error Or $iPID = 0 Then
        ShowError("启动失败", "无法启动 " & $TARGET_EXE)
        Exit(3)
    EndIf

    ; 等待窗口出现
    $hWnd = WinWait($TARGET_TITLE, "", 10)
    If $hWnd = 0 Then
        MsgBox(48, "警告", "程序已启动但未检测到窗口", 2)
        Return 0
    Else
        _BringWindowTopMost($hWnd)
        MsgBox(0, "成功", "程序启动成功。", 1)
        Return $hWnd
    EndIf
EndFunc

; ============= 业务流程函数 =============
; 初始化：确保 Connect 按钮流程
Func Init($hWnd)
    If $hWnd = 0 Then Return

    _BringWindowTopMost($hWnd)

    ; 如果已经是 DisConnect 状态，则认为已连接，直接返回
    Local $hButton = ControlGetHandle($hWnd, "", "WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
    If $hButton <> 0 Then
        Local $btnText = ControlGetText($hWnd, "", $hButton)
        If StringLower($btnText) = "disconnect" Then
            Return
        EndIf
    EndIf

    ; 等待并点击 Connect
    $hButton = WaitForControlEx($hWnd, "WindowsForms10.BUTTON.app.0.141b42a_r8_ad11", 10, True)
    _BringWindowTopMost($hWnd)
    ControlFocus($hWnd, "", $hButton)
    ControlClick($hWnd, "", $hButton)
    Sleep(2000)
EndFunc

; 设置 RF（基于 param1），并在日志区检索成功信息
Func SetRf($hWnd)
    If $hWnd = 0 Then Return

    _BringWindowTopMost($hWnd)

    ; 输入需要开启的 COM/数值（使用 param1）
    Local $hEdit = ControlGetHandle($hWnd, "", "WindowsForms10.EDIT.app.0.141b42a_r8_ad12")
    If $hEdit = 0 Then
        MsgBox(16, "错误", "未找到输入编辑框（WindowsForms10.EDIT.app.0.141b42a_r8_ad12）")
        Exit(1)
    EndIf

    ControlSetText($hWnd, "", $hEdit, "")
    Sleep(200)
    ControlSend($hWnd, "", $hEdit, $param1)

    ; 点击写入按钮
    Local $hWriteBtn = ControlGetHandle($hWnd, "", "WindowsForms10.BUTTON.app.0.141b42a_r8_ad12")
    If $hWriteBtn = 0 Then
        MsgBox(16, "错误", "未找到写入按钮（WindowsForms10.BUTTON.app.0.141b42a_r8_ad12）")
        Exit(1)
    EndIf
    _BringWindowTopMost($hWnd)
    ControlClick($hWnd, "", $hWriteBtn)

    ; 轮询日志区的最后一行
    Local $t0 = TimerInit()
    While True
        _BringWindowTopMost($hWnd)
        Local $logText = ControlGetText($hWnd, "", "WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad11")
        Local $lastLine = ""
        If $logText <> "" Then
            Local $lines = StringSplit($logText, @CRLF, 1)
            ; 从后往前找第一条非空
            For $i = $lines[0] To 1 Step -1
                If $lines[$i] <> "" Then
                    $lastLine = $lines[$i]
                    ExitLoop
                EndIf
            Next
        EndIf

        If $lastLine = "Set Attenuation to " & $param1 & " success." Then
            MsgBox(0, "Success", "目标信息已找到：" & $lastLine, 1)
            ExitLoop
        EndIf

        If TimerDiff($t0) >= 5000 Then
            MsgBox(16, "Error", "等待超时，未找到目标信息。", 1)
            Exit(1)
        EndIf
        Sleep(300)
    WEnd
EndFunc

; ============= 主程序开始 =============

; 检查命令行参数（允许1个数字或4个参数）
If $CmdLine[0] <> 1 And $CmdLine[0] <> 4 Then
    ShowError("参数错误", _
        "请提供以下两种参数格式之一：" & @CRLF & _
        "1. 单个数字参数" & @CRLF & _
        "2. 四个参数")
    Exit(1)
EndIf

; 参数处理
Global $param1, $param2, $param3, $param4
If $CmdLine[0] = 1 Then
    ; 单数字参数模式
    If Not StringIsDigit($CmdLine[1]) Then
        ShowError("参数类型错误", "单参数必须为数字")
        Exit(2)
    EndIf
    $param1 = Number($CmdLine[1])
Else
    ; 四参数模式（如后续需要，可在业务函数中使用）
    $param1 = $CmdLine[1]
    $param2 = $CmdLine[2]
    $param3 = $CmdLine[3]
    $param4 = $CmdLine[4]
EndIf

; 处理ACUControlTool程序（启动/附着并前置）
Local $hMain = HandleACUControlTool()
If $hMain = 0 Then
    ShowError("错误", "无法找到或拉起目标窗口。")
    Exit(10)
EndIf

; 初始化并设置 RF
Init($hMain)
SetRf($hMain)

; 收尾：可选地取消置顶，避免程序一直霸占最前
_CancelTopMost($hMain)

Exit(0) ; 正常退出
