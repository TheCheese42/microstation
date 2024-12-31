$LangDir = "microstation/langs"

Get-ChildItem "$LangDir\*.ts" | ForEach-Object {
    lupdate microstation/ -ts $_.FullName
}
