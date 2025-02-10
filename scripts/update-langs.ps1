$LangDir = "microstation/langs"

Get-ChildItem "$LangDir\*.ts" | ForEach-Object {
    lupdate -tr-function-alias translate=tr microstation/ microstation/gui.py microstation/devices.py microstation/actions/signals_slots.py -ts $_.FullName -no-obsolete -source-language en_US
}
