#cs ----------------------------------------------------------------------------
 AutoIt Version: 3.3.16.1
 Author:         myName

 Script Function:
	Auto control Sunvey.ControllerTool.exe, with topmost fix.
#ce ----------------------------------------------------------------------------

Opt("WinTitleMatchMode", 2) ; 允许部分匹配窗口标题

; === 辅助函数 ===
Func _BringWindowTopMost($title)
    If Not WinExists($title) Then Return False
    WinSetState($title, "", @SW_SHOW)
    WinSetState($title, "", @SW_RESTORE)
    WinActivate($title)
    WinSetOnTop($title, "", 1)
    WinWaitActive($title, "", 2)
    Sleep(120)
    Return True
EndFunc

Func _CancelTopMost($title)
    If WinExists($title) Then WinSetOnTop($title, "", 0)
EndFunc

; === 更新角度数据 ===
Func UpdateAngle($angle)
    If Not StringIsDigit(StringReplace($angle, "-", "")) Then
        MsgBox(16, "错误", "角度值无效: " & $angle)
        Return False
    EndIf

    Local $currentAngle = GetAngle()
    Local $angleDiff = Abs($currentAngle - Number($angle))
    Local $estimatedTime = Int($angleDiff / 60 * 1000) + 2000

    _BringWindowTopMost($windowTitle)
    ControlClick($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Sleep(100)
    ControlFocus($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", "^a")
    Sleep(50)
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", "{DEL}")
    Sleep(50)
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", $angle)
    Sleep(100)

    ControlClick($windowTitle, "", "WindowsForms10.BUTTON.app.0.141b42a_r39_ad14")
    Sleep(500)

    Local $startTime = TimerInit()
    Local $timeout = $estimatedTime + 5000
    Local $lastPrintTime = TimerInit()

    While TimerDiff($startTime) < $timeout
        Local $buttonState = ControlCommand($windowTitle, "", "WindowsForms10.BUTTON.app.0.141b42a_r39_ad14", "IsEnabled", "")
        If $buttonState Then ExitLoop

        If TimerDiff($lastPrintTime) >= 3000 Then
            $lastPrintTime = TimerInit()
        EndIf
        Sleep(1000)
    WEnd

    If TimerDiff($startTime) >= $timeout Then
        ConsoleWrite("移动超时，但继续执行" & @CRLF)
    EndIf

    Sleep(1000)
    Return True
EndFunc

; === 更新距离数据 ===
Func UpdateDistance($distance)
    _BringWindowTopMost($windowTitle)
    ControlFocus($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13")
    ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", "^a")
    Sleep(100)
    ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", "{DEL}")
    Sleep(100)
    ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", $distance)
    Sleep(100)
    ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad16")
EndFunc

; === 获取角度与距离 ===
Func GetAngle()
    _BringWindowTopMost($windowTitle)
    ControlClick($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Local $currentAngle = ControlGetText($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Sleep(500)
    Return $currentAngle
EndFunc

Func GetDistance()
    _BringWindowTopMost($windowTitle)
    ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad14")
    Local $currentDistance = ControlGetText($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r8_ad13")
    Sleep(500)
    Return $currentDistance
EndFunc

Func GetData()
    Local $currentAngle = GetAngle()
    Local $currentDistance = GetDistance()
    Local $result = $currentAngle & "|" & $currentDistance
    ConsoleWrite($result & @CRLF)
EndFunc

; === 主逻辑 ===
Local $softwarePath = "Sunvey.ControllerTool.exe"
Local $windowTitle = "System24"

If WinExists($windowTitle) Then
    WinActivate($windowTitle)
    _BringWindowTopMost($windowTitle)
    MsgBox(0, "提示", "软件已经在运行中！", 1)
Else
    Run($softwarePath)
    WinWait($windowTitle, "", 10)
    _BringWindowTopMost($windowTitle)
EndIf

Local $distanceData = ""
Local $angleData = ""

For $i = 1 To $CmdLine[0]
    If $CmdLine[$i] = "-distance" And $i + 1 <= $CmdLine[0] Then
        $distanceData = $CmdLine[$i + 1]
    ElseIf $CmdLine[$i] = "-angle" And $i + 1 <= $CmdLine[0] Then
        $angleData = $CmdLine[$i + 1]
    EndIf
Next

If $distanceData <> "" Then
    _BringWindowTopMost($windowTitle)
    UpdateDistance($distanceData)
    Sleep(1000)
EndIf

If $angleData <> "" Then
    _BringWindowTopMost($windowTitle)
    Local $currentAngle = GetAngle()
    UpdateAngle($angleData)
    If IsNumber($currentAngle) Or StringIsDigit($currentAngle) Then
        Local $gap = Abs(Number($currentAngle) - Number($angleData))
        MsgBox(0,"","旋转的角度为 :" & $gap,1)
        Sleep(1000 * $gap / 6)
    Else
        MsgBox(0,"","当前角度获取失败",1)
    EndIf
EndIf

GetData()
_CancelTopMost($windowTitle)
MsgBox(0,"","Done",1)
