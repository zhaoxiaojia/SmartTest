# SmartTest has a local top-level `jira` package. PyInstaller's bundled
# third-party `jira` hook expects pip distribution metadata, which the local
# package intentionally does not have.
datas = []
hiddenimports = []
