#!/bin/bash

LANG_DIR="microstation/langs"

for lang_file in "$LANG_DIR"/*.ts; do
    lupdate microstation/ -ts "$lang_file"
done
