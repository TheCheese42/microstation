nuitka \
    --standalone \
    --onefile \
    --python-flag="no_asserts" \
    --python-flag="no_docstrings" \
    --python-flag="-m" \
    --main="microstation" \
    --prefer-source-code \
    --output-dir="build/" \
    --linux-icon="microstation/icons/aperture.png" \
    --product-name="Microstation" \
    --product-version="$(cat microstation/version.txt)" \
    --file-version="$(cat microstation/version.txt)" \
    --include-data-dir="microstation/arduino/=arduino/" \
    --include-data-dir="microstation/external_styles/=external_styles/" \
    --include-data-dir="microstation/icons/=icons/" \
    --include-data-dir="microstation/langs/=langs/" \
    --include-data-dir="microstation/ui/=ui/" \
    --include-data-file="microstation/version.txt=version.txt" \
    --enable-plugin=pyqt6 \
