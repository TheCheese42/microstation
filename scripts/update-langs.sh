#!/bin/bash

LANG_DIR="microstation/langs"

for lang_file in "$LANG_DIR"/*.ts; do
    lupdate -tr-function-alias translate=tr microstation/ microstation/gui.py microstation/devices.py -ts $lang_file -no-obsolete -source-language en_US
done
