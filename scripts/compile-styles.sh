deactivate || true
mkdir style_clones
cd style_clones
git clone https://github.com/Alexhuszagh/BreezeStyleSheets
cd BreezeStyleSheets
python -m venv .venv
source .venv/bin/activate
pip install PySide6
python configure.py --styles=all --extensions=all --qt-framework pyqt6 --resource breeze.qrc --compiled-resource "breeze_pyqt6.py"
mkdir -p ../../microstation/external_styles/breeze
cp -f LICENSE.md ../../microstation/external_styles/breeze/
cp -rf dist/* ../../microstation/external_styles/breeze/
cp -f resources/breeze_pyqt6.py ../../microstation/external_styles/breeze/
rm -rf ../../microstation/external_styles/breeze/*-alt
deactivate
cd ../../
rm -rf style_clones
if [ ! -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
