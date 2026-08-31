# Android APK Signing

SmartTest signs `mobile/android` with platform keys for privileged DUT cases.
Signing material must stay local and must not be committed to git.

## Local Signing Files

Put the platform signing package on each build machine through a private channel.
The default local layout is:

```text
mobile/android/signapk/mnt/fileroot/fae.autobuild/workdir/workspace/FAE/AutoBuild/IPTV/daxiong.cao/s6/u-1/
  build/target/product/security/platform.x509.pem
  build/target/product/security/platform.pk8
  prebuilts/sdk/tools/lib/signapk.jar
```

`mobile/android/signapk/` and `mobile/android/signapk.zip` are ignored by git.

If the files live somewhere else, set these environment variables:

```bash
export SMARTTEST_SIGNAPK_DIR="/absolute/path/to/u-1"
```

Or set every file explicitly:

```bash
export SMARTTEST_PLATFORM_CERT_PEM="/absolute/path/platform.x509.pem"
export SMARTTEST_PLATFORM_CERT_PK8="/absolute/path/platform.pk8"
export SMARTTEST_SIGNAPK_JAR="/absolute/path/signapk.jar"
```

## macOS Build

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python core/devtools/scripts/init_venv.py

cd mobile/android
./gradlew :app:assembleDebug
cd ..
python -c "from mobile import android; android.sign_privileged_apk()"
python mobile/scripts/build_apk.py
```

The signed APK is written to:

```text
mobile/android/app/build/outputs/apk/debug/app-debug-platform.apk
dist/mobile/app-debug-platform.apk
```

Desktop packaging entrypoints are under `client/scripts/`. macOS installer packaging is not wired in this repository yet; `build_installer.py` currently supports the Windows installer flow and exits with a macOS-specific message.
