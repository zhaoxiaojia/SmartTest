import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

import env


def preserve_dynamic_bridge_translations(ts_file_path: str):
    tree = ET.parse(ts_file_path)
    root = tree.getroot()
    changed = False
    for message in root.findall(".//message"):
        source = message.find("source")
        translation = message.find("translation")
        if source is None or translation is None:
            continue
        text = source.text or ""
        if not (text.startswith("test.param.") or text.startswith("test.schema.")):
            continue
        if message.get("type") == "vanished":
            message.attrib.pop("type", None)
            changed = True
        if translation.get("type") == "vanished":
            translation.attrib.pop("type", None)
            changed = True
    if changed:
        tree.write(ts_file_path, encoding="utf-8", xml_declaration=True)


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
        preserve_dynamic_bridge_translations(tsFilePath)
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
            os.path.join(example_project_dir, "bridge", "HomeBridge.py"),
            os.path.join(example_project_dir, "bridge", "JiraBridge.py"),
            os.path.join(example_project_dir, "bridge", "DebugBridge.py"),
            os.path.join(example_project_dir, "bridge", "ReportBridge.py"),
            os.path.join(example_project_dir, "bridge", "RunBridge.py"),
            os.path.join(example_project_dir, "bridge", "TestPageBridge.py"),
            os.path.join(example_project_dir, "bridge", "ToolBridge.py"),
            os.path.join(example_project_dir, "bridge", "RedmineBridge.py"),
        ],
    )
