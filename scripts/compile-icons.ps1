pyrcc5 microstation/icons/icons.qrc --output microstation/icons/resource.py
(Get-Content microstation/icons/resource.py) -replace 'PyQt5', 'PyQt6' | Set-Content microstation/icons/resource.py
