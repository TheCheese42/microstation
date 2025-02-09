$LangDir = "microstation/langs"

Get-ChildItem "$LangDir\*.ts" | ForEach-Object {
    lupdate -tr-function-alias translate=tr microstation/ microstation/gui.py microstation/devices.py -ts $_.FullName -no-obsolete -source-language en_US
}
