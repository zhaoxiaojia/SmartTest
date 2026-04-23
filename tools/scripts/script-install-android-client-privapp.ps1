param(
    [string]$Adb = "adb",
    [string]$Serial = "",
    [string]$ApkPath = "D:\SmartTest\android_client\app\build\outputs\apk\debug\app-debug.apk",
    [string]$PackageName = "com.smarttest.mobile",
    [string]$AppDirName = "SmartTestMobile",
    [string]$PrivAppRoot = "/system/priv-app",
    [string]$PermissionsDir = "/system/etc/permissions",
    [switch]$SkipReboot
)

$ErrorActionPreference = "Stop"

function Join-AdbCommand {
    param([string[]]$Args)
    if ([string]::IsNullOrWhiteSpace($Serial)) {
        return @($Adb) + $Args
    }
    return @($Adb, "-s", $Serial) + $Args
}

function Invoke-Adb {
    param(
        [string[]]$Args,
        [switch]$AllowFailure
    )
    $command = Join-AdbCommand -Args $Args
    Write-Host "[privapp] $($command -join ' ')"
    & $command[0] $command[1..($command.Length - 1)]
    if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
        throw "adb command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Su {
    param(
        [string]$Command,
        [switch]$AllowFailure
    )
    Invoke-Adb -Args @("shell", "su", "-c", $Command) -AllowFailure:$AllowFailure
}

$resolvedApkPath = (Resolve-Path $ApkPath).Path
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$permissionsXml = Join-Path $repoRoot "android_client\system_app\privapp-permissions-com.smarttest.mobile.xml"
$resolvedPermissionsXml = (Resolve-Path $permissionsXml).Path

$remoteApk = "/data/local/tmp/$AppDirName.apk"
$remoteXml = "/data/local/tmp/privapp-permissions-com.smarttest.mobile.xml"
$targetApkDir = "$PrivAppRoot/$AppDirName"
$targetApk = "$targetApkDir/$AppDirName.apk"
$targetXml = "$PermissionsDir/privapp-permissions-com.smarttest.mobile.xml"

Write-Host "[privapp] package=$PackageName"
Write-Host "[privapp] apk=$resolvedApkPath"
Write-Host "[privapp] xml=$resolvedPermissionsXml"
Write-Host "[privapp] target_apk=$targetApk"
Write-Host "[privapp] target_xml=$targetXml"

Invoke-Adb -Args @("push", $resolvedApkPath, $remoteApk)
Invoke-Adb -Args @("push", $resolvedPermissionsXml, $remoteXml)

Invoke-Su "mkdir -p '$targetApkDir'"
Invoke-Su "cp '$remoteApk' '$targetApk'"
Invoke-Su "cp '$remoteXml' '$targetXml'"
Invoke-Su "chown root:root '$targetApk' '$targetXml'"
Invoke-Su "chmod 0644 '$targetApk' '$targetXml'"
Invoke-Su "restorecon '$targetApk' '$targetXml'" -AllowFailure
Invoke-Su "pm uninstall '$PackageName'" -AllowFailure

if (-not $SkipReboot) {
    Invoke-Adb -Args @("reboot")
    Write-Host "[privapp] reboot issued; verify after boot:"
    Write-Host "[privapp] adb shell dumpsys package $PackageName | findstr /i ""codePath grantedPermissions android.permission.REBOOT"""
} else {
    Write-Host "[privapp] reboot skipped; reboot device manually before verification"
}
