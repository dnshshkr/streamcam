import os
import PyInstaller.utils.hooks as hooks

# Patterns of dynamic library filenames that might be bundled with some installed Python packages.
# extended to cover the unsually named pylon-libusb
hooks.PY_DYLIB_PATTERNS = [
    '*.dll',
    '*.dylib',
    'lib*.so',
    'pylon*.so',
]


# Collect dynamic libs as data (to prevent pyinstaller from modifying them)
datas = hooks.collect_dynamic_libs('pypylon')

# Collect data files, looking for pypylon/pylonCXP/bin/ProducerCXP.cti, but other files may also be needed
datas += hooks.collect_data_files('pypylon')

# Exclude the C++-extensions from automatic search, add them manually as data files
# their dependencies were already handled with collect_dynamic_libs
excludedimports = ['pypylon._pylon', 'pypylon._genicam']
for filename, module in hooks.collect_all('pypylon._pylon')[0]:
    print(filename, module)
    if (os.path.basename(filename).startswith('_pylon.')
            or os.path.basename(filename).startswith('_genicam.')):
        datas += [(filename, module)]