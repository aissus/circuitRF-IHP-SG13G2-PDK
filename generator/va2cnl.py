#!/usr/bin/env python3
"""Turn a generated .va parameter file into one line of .cnl instance params."""
import re, sys
src = open(sys.argv[1]).read()
pars = re.findall(r"^parameter\s+real\s+(\w+)\s*=\s*([-\w.+eE]+)\s*;", src, re.M)
print("  ".join(f"{k}={v}" for k, v in pars))
