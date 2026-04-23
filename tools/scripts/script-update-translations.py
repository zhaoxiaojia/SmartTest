import os
import shutil
import subprocess

import env


# noinspection PyPep8Naming
def generateTranslations(projectName: str, localeDatas, files=None):
    if not files:
        files = []
    project_dir = env.uiProjectPath(projectName)
    targetFolder = os.path.join(project_dir, 'imports', projectName, 'i18n')
    for locale in localeDatas:
        tsFileName = f"{projectName}_{locale}.ts"
        qmFileName = f"{projectName}_{locale}.qm"
        tsFilePath = os.path.join(project_dir, tsFileName)
        qmFilePath = os.path.join(project_dir, qmFileName)
        commands = [env.pyside6_lupdate(), os.path.join(project_dir, 'imports', "resource.qrc")]
        for file in files:
            commands.append(file)
        commands.append("-ts")
        commands.append(tsFilePath)
        subprocess.run(commands, check=True)
        subprocess.run([env.pyside6_lrelease(), tsFilePath], check=True)
        os.makedirs(targetFolder, exist_ok=True)
        shutil.copy(qmFilePath, os.path.join(targetFolder, qmFileName))


if __name__ == "__main__":
    generateTranslations("FluentUI", ["en_US", "zh_CN"])
    example_project_dir = env.uiProjectPath(env.projectName)
    generateTranslations(
        env.projectName,
        ["en_US", "zh_CN"],
        [
            os.path.join(example_project_dir, "helper", "InitializrHelper.py"),
            os.path.join(example_project_dir, "bridge", "AuthBridge.py"),
            os.path.join(example_project_dir, "bridge", "JiraBridge.py"),
            os.path.join(example_project_dir, "bridge", "RunBridge.py"),
            os.path.join(example_project_dir, "bridge", "TestPageBridge.py"),
        ],
    )
