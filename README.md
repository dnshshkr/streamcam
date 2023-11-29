# streamcam
for windows: `pyinstaller --onefile --additional-hooks-dir=. --collect-submodules <path-to-pypylon> streamcam.py`

for linux: `pyinstaller --onefile --additional-hooks-dir=. streamcam.py`

replace `hook-pypylon.py` in stdhooks in Pyinstaller hooks