#!/bin/bash

UI_DIR="microstation/ui"

for ui_file in "$UI_DIR"/*.ui; do
    filename=$(basename "$ui_file" .ui)
    pyuic6 "$ui_file" -o "$UI_DIR/${filename}_ui.py"
done
