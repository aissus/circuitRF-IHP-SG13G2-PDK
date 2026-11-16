"""osdi-load.py <glob>: load each compiled model as a shared library on this machine and read its OSDI
exports, so a build that would not load in circuitRF here fails (a missing DLL or symbol, a wrong format)."""
import ctypes, glob, os, sys

files = sorted(glob.glob(sys.argv[1]))
assert files, f'no builds match {sys.argv[1]}'
for f in files:
    lib = ctypes.CDLL(os.path.abspath(f))
    u = lambda name: ctypes.c_uint32.in_dll(lib, name).value
    print(f'{f}: loads, OSDI {u("OSDI_VERSION_MAJOR")}.{u("OSDI_VERSION_MINOR")}, {u("OSDI_NUM_DESCRIPTORS")} model(s)')
