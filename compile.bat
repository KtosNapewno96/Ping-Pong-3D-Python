@echo off
nuitka --standalone --jobs=3 --windows-console-mode=disable --include-package=ursina --output-dir=build PingPong3DRealisticV1.3.1.py