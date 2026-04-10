import shutil
import os
import subprocess

import env

if __name__ == "__main__":
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    buildDir = os.path.join('.', 'build')
    distDir = os.path.join('.', 'dist')
    try:
        shutil.rmtree(buildDir)
        shutil.rmtree(distDir)
    except FileNotFoundError:
        pass

    # Refresh i18n and QRC outputs first so packaged app is up to date.
    subprocess.run([env.python(), os.path.join(scripts_dir, 'script-update-translations.py')], check=True)
    subprocess.run([env.python(), os.path.join(scripts_dir, 'script-update-resource.py')], check=True)

    repo_root = os.path.abspath(".")
    path = os.path.join(repo_root, 'main.py')
    assets_dir = os.path.join(repo_root, "tools", "packaging", "assets")
    args = [
        env.nuitka(),
        "--standalone",
        "--disable-console",
        "--show-progress",
        "--plugin-enable=pyside6",
        "--include-qt-plugins=qml",
        f"--macos-app-icon={os.path.join(assets_dir, 'favicon.icns')}",
        f"--linux-icon={os.path.join(assets_dir, 'favicon.jpg')}",
        f"--windows-icon-from-ico={os.path.join(assets_dir, 'SmartTest.ico')}",
        f"--output-filename=SmartTest",
        path
    ]
    subprocess.run(args, env=env.environment(), check=True)
    os.rename("main.build", "build")
    os.rename("main.dist", "dist")
    excludeFiles = [
        'qt6location',
        'qt6webchannel',
        'qt6webenginequick',
        'qt6webenginequickdelegatesqml',
        'qt6websockets',
        'qt6virtualkeyboard',
        'qt6pdfquick',
        'qt6pdf',
        'qt6quicktimeline',
        'qt6datavisualizationqml',
        'qt6datavisualization',
        'qt6charts',
        'qt6chartsqml',
        'qt6webenginecore',
        'qt6quick3d',
        'qt6quick3dassetimport',
        'qt6quick3d',
        'qt6quick3dassetutils',
        'qt6quick3deffects',
        'qt6quick3dhelpers',
        'qt6quick3dparticleeffects',
        'qt6quick3dparticles',
        'qt6quick3druntimerender',
        'qt6quick3d',
        'qt6quick3dutils'
    ]
    for root, dirs, files in os.walk(distDir):
        for fileName in files:
            filePath = os.path.join(root, fileName)
            print(f'Deleted: {filePath}')
            for excludeFile in excludeFiles:
                if excludeFile in filePath:
                    try:
                        os.remove(filePath)
                    except FileNotFoundError:
                        pass
