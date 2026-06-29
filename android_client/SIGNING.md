# Android APK Signing

SmartTest signs `android_client` with platform keys for privileged DUT cases.
Signing material must stay local and must not be committed to git.

## Local Signing Files

Put the platform signing package on each build machine through a private channel.
The default local layout is:

```text
android_client/signapk/mnt/fileroot/fae.autobuild/workdir/workspace/FAE/AutoBuild/IPTV/daxiong.cao/s6/u-1/
  build/target/product/security/platform.x509.pem
  build/target/product/security/platform.pk8
  prebuilts/sdk/tools/lib/signapk.jar
```

`android_client/signapk/` and `android_client/signapk.zip` are ignored by git.

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
python tools/scripts/script-init-venv.py

cd android_client
./gradlew :app:assembleDebug
cd ..
python -c "import android_client; android_client.sign_privileged_apk()"
python tools/scripts/script-build-apk.py
```

The signed APK is written to:

```text
android_client/app/build/outputs/apk/debug/app-debug-platform.apk
dist_installer/app-debug-platform.apk
```

Desktop packaging entrypoints are under `tools/scripts/`. macOS installer packaging is not wired in this repository yet; `script-build-installer.py` currently supports the Windows installer flow and exits with a macOS-specific message.
