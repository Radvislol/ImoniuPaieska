# set_encoding_hook.py
import os
import sys

# Nustatykite konsolės kodavimą į UTF-8, jei jis dar nenustatytas
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Taip pat nustatykite aplinkos kintamąjį, kaip papildomą saugiklį
os.environ['PYTHONIOENCODING'] = 'utf-8'