$UiDir = "microstation/ui"

Get-ChildItem "$UiDir\*.ui" | ForEach-Object {
    $filename = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
    pyuic6 $_.FullName -o "$UiDir\$filename`_ui.py"
}
