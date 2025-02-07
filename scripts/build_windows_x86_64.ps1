nuitka `
    --standalone `
    --onefile `
    --python-flag="no_asserts" `
    --python-flag="no_docstrings" `
    --python-flag="-m" `
    --main="microstation" `
    --prefer-source-code `
    --output-dir="build\" `
    --windows-console-mode="attach" `
    --windows-icon-from-ico="microstation\icons\aperture.ico" `
    --product-name="Microstation" `
    --product-version="$(Get-Content microstation\version.txt)" `
    --file-version="$(Get-Content microstation\version.txt)" `
    --include-data-dir="microstation\arduino\=arduino\" `
    --include-data-dir="microstation\external_styles\=external_styles\" `
    --include-data-dir="microstation\icons\=icons\" `
    --include-data-dir="microstation\langs\=langs\" `
    --include-data-dir="microstation\ui\=ui\" `
    --enable-plugin=pyqt6 `
