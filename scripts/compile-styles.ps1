deactivate
mkdir style_clones
cd style_clones
git clone https://github.com/Alexhuszagh/BreezeStyleSheets
cd BreezeStyleSheets
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install PySide6
python configure.py --styles=all --extensions=all --qt-framework pyqt6 --resource breeze.qrc --compiled-resource "breeze_pyqt6.py"
mkdir -p ../../microstation/external_styles/breeze
Copy-Item -Fo LICENSE.md ../../microstation/external_styles/breeze/
Copy-Item -R -Fo dist/* ../../microstation/external_styles/breeze/
Copy-Item -Fo resources/breeze_pyqt6.py ../../microstation/external_styles/breeze/
Remove-Item -Recurse -Force ../../microstation/external_styles/breeze/*-alt
deactivate
cd ../../
Remove-Item -Recurse -Force style_clones
. .venv/Scripts/Activate.ps1
