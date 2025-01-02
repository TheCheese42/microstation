# Arduino CLI Usage notes

## Get Board Type

```sh
arduino-cli board list
```

Scrape output.

## Install additional Boards

```sh
arduino-cli core install <FQBN>
```

## Compile Sketch

Always required before uploading.

```sh
arduino-cli compile --fqbn <FQBN> <path/to/folder_containing_ino_file>
# Optional: Add --build-path flag to save in a specified directory
```

## Upload Sketch

```sh
arduino-cli upload --port <port> --fqbn <FQBN> <path/to/folder_containing_hex_file>
```

## Install libraries

```sh
arduino-cli lib update-index

# Search
arduino-cli lib search <lib>

# Install
arduino-cli lib install <lib>

# Upgrade
arduino-cli lib upgrade
```
