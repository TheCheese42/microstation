pyrcc5 microstation/icons/icons.qrc -o microstation/icons/resource.py
sed -i 's/PyQt5/PyQt6/g' microstation/icons/resource.py