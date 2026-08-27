import os
import subprocess

import env


# noinspection PyPep8Naming
def generateResource(_projectName):
    project_dir = env.uiProjectPath(_projectName)
    subprocess.run([
        env.pyside6_rcc(),
        os.path.join(project_dir, 'imports', 'resource.qrc'),
        "-o",
        os.path.join(project_dir, 'imports', 'resource_rc.py')
    ], check=True)


if __name__ == "__main__":
    generateResource("FluentUI")
    generateResource(env.projectName)
