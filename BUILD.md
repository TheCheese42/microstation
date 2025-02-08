# Build Microstation

Microstation is a PyQt6 app. To run Microstation, the following things need to be done:

- Compile the UI to .py files
- Compile the Icons to a resource.py file
- Compile the Language .ts files to .qm files
- Compile the external styles

You can also compile an executable using nuitka, and a Windows Installer file using WiX.

Microstation requires Python 3.12 or higher to work.

## Linux

### Prerequisites

The following packages need to be installed to compile and run Microstation, per distribution.

#### Debian

```sh
sudo apt update
sudo apt upgrade
sudo apt install git  # General
sudo apt install pyqt5-dev-tools qtchooser qttools5-dev-tools  # Compile resources
sudo apt install patchelf ccache  # Compile with nuitka
sudo apt install libxcb-cursor0 libcairo-dev libgirepository1.0-dev  # Runtime dependencies
sudo apt install gir1.2-appindicator3-0.1  # GNOME runtime dependency
```

> Note:
> The libcairo-dev and libgirepository1.0-dev dependencies are Debian only, according to <https://pystray.readthedocs.io/en/latest/faq.html>.

#### RedHat

```sh
sudo dnf upgrade --refresh
sudo dnf install git  # General
sudo dnf install python3-qt5 mingw64-qt-qmake  # Compile resources
sudo dnf install patchelf ccache  # Compile with nuitka
sudo dnf install xcb-util-cursor  # Runtime dependencies
```

#### Arch

```sh
sudo pacman -Syu
sudo pacman -S git  # General
sudo pacman -S python-pyqt5 qt5-tools  # Compile resources
sudo pacman -S patchelf ccache  # Compile with nuitka
sudo pacman -S xcb-util-cursor  # Runtime dependencies
```

### Downloading the source files

```sh
git clone https://github.com/TheCheese42/microstation
```

### Compiling Data

```sh
cd microstation  # cd into the cloned folder
python -m venv .venv  # At least Python 3.12
source .venv/bin/activate
pip install -r requirements.txt -r dev-requirements.txt
pip install PyGObject  # To allow using the AppIndicator systray backend on Linux
source scripts/compile-ui.sh  # Required
source scripts/compile-icons.sh  # Optional, otherwise no icons will be shown
source scripts/compile-langs.sh  # Optional, otherwise only english will be available
source scripts/compile-styles.sh  # Optional, otherwise only the default style will be available
```

### Run Microstation

Now you can already run Microstation.

```sh
# Run from within the cloned microstation/ folder
python -m microstation
```

### Bundle Executable

Finally, you can also bundle everything into an executable. For that, we use [nuitka](https://nuitka.net).

```sh
# Run from within the cloned microstation/ folder
source scripts/build_linux_x86_64.sh
```

> Note:
> If you encounter a weird error with the line
> `FATAL: Failed unexpectedly in Scons C backend compilation.`
> You can try adding `--clang` to the `scripts/build_linux_x86_64.sh` script.
> Of course you also need to install clang using your package manager.

The resulting executable can be found at `build/microstation.bin`.

## Windows

### Prerequisites

- Install a Python version of at least 3.12 from <https://www.python.org/downloads/>
- Install git from <https://git-scm.com/downloads/win>

### Downloading the source files

```pwsh
git clone https://github.com/TheCheese42/microstation
```

### Compiling Data

```pwsh
Set-Location .\microstation  # cd into the cloned folder
python -m venv .venv  # At least Python 3.12
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r dev-requirements.txt
.\scripts\compile-ui.ps1  # Required
Set-Alias -Name rcc -Value .\.venv\Lib\site-packages\qt6_applications\Qt\bin\rcc.exe  # Make the rcc.exe tool available
.\scripts\compile-icons.ps1  # Optional, otherwise no icons will be shown
Set-Alias -Name lrelease -Value .\.venv\Lib\site-packages\qt6_applications\Qt\bin\lrelease.exe  # Make the lrelease.exe tool available
.\scripts\compile-langs.ps1  # Optional, otherwise only english will be available
.\scripts\compile-styles.ps1  # Optional, otherwise only the default style will be available
```

### Run Microstation

Now you can already run Microstation.

```pwsh
# Run from within the cloned microstation\ folder
python -m microstation
```

### Bundle Executable

Finally, you can also bundle everything into an executable. For that, we use [nuitka](https://nuitka.net).

```pwsh
# Run from within the cloned microstation\ folder
.\scripts\build_windows_x86_64.ps1
```

The resulting executable can be found at `build\microstation.exe`.

### Bundle Installer

Lastly, it's possible to create a Windows Install file using WiX.

To be added.
