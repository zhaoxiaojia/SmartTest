import sys
import os
import shutil

projectName = "example"


# noinspection PyPep8Naming
def _scriptsPath():
    venv_dir = _venvDir()
    if sys.platform.startswith("win"):
        return os.path.join(venv_dir, "Scripts")
    return os.path.join(venv_dir, "bin")


def _venvDir():
    # Prefer ".venv" (common convention). Fall back to "venv" for compatibility.
    if os.path.isdir(os.path.join(".", ".venv")):
        return os.path.join(".", ".venv")
    return os.path.join(".", "venv")


def uiRoot():
    return os.path.join(".", "ui")


def uiProjectPath(name: str):
    return os.path.join(uiRoot(), name)


# noinspection PyPep8Naming
def _pathSeparator():
    if sys.platform.startswith("darwin"):
        return ":"
    return ";"

def pip():
    if sys.platform.startswith("win"):
        return os.path.join(_scriptsPath(), "pip.exe")
    return os.path.join(_scriptsPath(), "pip")


def pyinstaller():
    if sys.platform.startswith("win"):
        return os.path.join(_scriptsPath(), "pyinstaller.exe")
    return os.path.join(_scriptsPath(), "pyinstaller")


def nuitka():
    if sys.platform.startswith("win"):
        return os.path.join(_scriptsPath(), 'nuitka.bat')
    return os.path.join(_scriptsPath(), 'nuitka')


def python():
    if sys.platform.startswith("win"):
        return os.path.join(_scriptsPath(), "python.exe")
    return os.path.join(_scriptsPath(), "python")


def pyside6_rcc():
    name = "pyside6-rcc.exe" if sys.platform.startswith("win") else "pyside6-rcc"
    local = os.path.join(_scriptsPath(), name)
    return local if os.path.isfile(local) else (shutil.which(name) or local)


# noinspection SpellCheckingInspection
def pyside6_lupdate():
    name = "pyside6-lupdate.exe" if sys.platform.startswith("win") else "pyside6-lupdate"
    local = os.path.join(_scriptsPath(), name)
    return local if os.path.isfile(local) else (shutil.which(name) or local)


# noinspection SpellCheckingInspection
def pyside6_lrelease():
    name = "pyside6-lrelease.exe" if sys.platform.startswith("win") else "pyside6-lrelease"
    local = os.path.join(_scriptsPath(), name)
    return local if os.path.isfile(local) else (shutil.which(name) or local)


# noinspection PyPep8Naming
def environment():
    environ = os.environ.copy()
    current = os.environ.get('PYTHONPATH', '')
    workPath = os.path.dirname(os.path.abspath(__file__))
    if current != '':
        workPath = workPath + _pathSeparator() + current
    environ["PYTHONPATH"] = workPath
    return environ
