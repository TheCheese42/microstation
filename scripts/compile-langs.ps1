$LangDir = "microstation/langs"

Get-ChildItem "$LangDir\*.ts" | ForEach-Object {
    lrelease $_.FullName
}
