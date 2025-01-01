deactivate
mkdir style_clones
cd style_clones
git clone https://github.com/Alexhuszagh/BreezeStyleSheets
cd BreezeStyleSheets
python -m venv .venv
source .venv/bin/activate
pip install PySide6
python configure.py --styles=all --extensions=all --qt-framework pyqt6 --resource breeze.qrc --compiled-resource "breeze_pyqt6.py"
cp -r dist/* ../../microstation/external_styles/
cp resource/breeze_pyqt6.py ../../microstation/external_styles/
deactivate
cd ../../
rm -rf style_clones
source .venv/bin/activate
