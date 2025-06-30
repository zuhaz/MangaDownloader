# MangaDownloader

A lightweight desktop app to download manga from multiple online sources.  

# Technology used
Built with Python, CustomTkinter, and packaged with PyInstaller.

---

## Features

- Simple and responsive GUI
- Supports multiple providers: MangaHere, MangaPark, MangaPill
- More providers will be added in future updates
- Single-file Windows executable available under [Releases](https://github.com/zuhaz/MangaDownloader)

---

## Getting Started

### Run from source

```bash
git clone https://github.com/zuhaz/MangaDownloader.git
cd MangaDownloader

python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On Linux/macOS

pip install -r requirements.txt
python main.py
```

### Build executable

```bash
pyinstaller --onefile --windowed main.py --icon=assets/logo.ico --add-data "assets/logo.ico;assets"
```

Output will be in the `dist/` folder.

---

## License

Licensed under the [Apache License 2.0](LICENSE).
