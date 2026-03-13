# xv6 Filesystem Reader

Tool to **read and write** disk images of the [xv6](https://github.com/mit-pdos/xv6-riscv) file system. Mount the image with FUSE on Linux, extract its contents to disk, or edit files inside the image.

---

## Academic context

This project is used in the **Operating Systems** course at **FaMAF – UNC** (Facultad de Matemática, Astronomía, Física y Computación, Universidad Nacional de Córdoba).

It lets you inspect and modify xv6 disk images (e.g. `fs.img`) from Linux without running xv6: mount the file system, list directories, read and edit files, and save changes back to the image.

---

## Features

- **Read**: list directories, read files and device nodes from the xv6 file system.
- **Write**: modify existing files; changes are persisted to the image when using the `--write` option when mounting.
- **FUSE mount**: use the image as a directory on Linux (`ls`, `cat`, editors, etc.).
- **Extract**: dump the entire file system contents to a local directory (`./root/`).
- **Easy install**: install via `pip` or `pipx`; two commands: `xv6fs` (mount) and `xv6fs-extract` (extract).

---

## Requirements

- **Python** 3.7 or newer.
- **libfuse** (to mount the file system).  
  On Debian/Ubuntu:
  ```bash
  sudo apt install libfuse-dev
  ```

---

## Installation

### With pipx (recommended)

From the project directory:

```bash
pipx install .
```

The commands `xv6fs` and `xv6fs-extract` will be available on your PATH.

### With pip (virtualenv or development)

```bash
pip install -e .
```

To include publish dependencies (build, twine) as well:

```bash
pip install -e ".[dev]"
```

---

## Usage

### Mount the image (FUSE)

Mount the image as a directory. You can use `ls`, `cat`, editors, etc.

```bash
# Read-only (default)
xv6fs fs.img /mnt/xv6

# Read and write (changes are saved to the image)
xv6fs fs.img /mnt/xv6 --write
```

The mount point must exist; create it if needed:

```bash
mkdir -p /mnt/xv6
xv6fs fs.img /mnt/xv6 --write
```

To unmount:

```bash
fusermount -u /mnt/xv6
```

### Extract to disk

Extract the full file system contents into the current directory under `./root/`:

```bash
xv6fs-extract fs.img
```

This creates the directory tree and files under `./root/` (e.g. `./root/init`, `./root/etc/hostname`, etc.).

---

## Publishing to PyPI

To publish the package to PyPI (project maintainers):

1. Install publish dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

2. Configure PyPI credentials (token at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)) in `~/.pypirc` or via environment variables.

3. Run the script from the project root (with your venv activated if you use one):
   ```bash
   chmod +x scripts/publish_to_pypi.sh
   ./scripts/publish_to_pypi.sh           # publish to PyPI
   ./scripts/publish_to_pypi.sh --test    # publish to Test PyPI
   ./scripts/publish_to_pypi.sh --build-only   # only build dist/, do not upload
   ```

---

## License

MIT.
