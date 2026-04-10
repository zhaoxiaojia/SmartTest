import subprocess
import sys
import os

import env

if __name__ == "__main__":
    isFast = False
    args = sys.argv
    if len(args) >= 2:
        if "fast" in args[1:]:
            isFast = True
    if not isFast:
        cmd1 = [env.python(), os.path.join(".", "script-update-translations.py")]
        print("RUN:", cmd1)
        r1 = subprocess.run(cmd1)
        print("RC :", r1.returncode)

        cmd2 = [env.python(), os.path.join(".", "script-update-resource.py")]
        print("RUN:", cmd2)
        r2 = subprocess.run(cmd2)
        print("RC :", r2.returncode)

    cmd3 = [env.python(), os.path.join(".", env.projectName, "main.py")]
    print("RUN:", cmd3)
    r3 = subprocess.run(cmd3, env=env.environment())
    print("RC :", r3.returncode)
