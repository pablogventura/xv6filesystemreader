#!/usr/bin/env bash
# Publish the package to PyPI (or Test PyPI with --test).
# Requirements: pip install build twine (or pip install -e ".[dev]")
#
# Usage:
#   ./scripts/publish_to_pypi.sh           # publish to PyPI
#   ./scripts/publish_to_pypi.sh --test    # publish to Test PyPI (https://test.pypi.org)
#   ./scripts/publish_to_pypi.sh --build-only   # only build dist/ (sdist + wheel)

set -e
cd "$(dirname "$0")/.."

BUILD_ONLY=false
REPO=""
for arg in "$@"; do
    case "$arg" in
        --test)        REPO="--repository testpypi" ;;
        --build-only)  BUILD_ONLY=true ;;
        -h|--help)
            echo "Usage: $0 [--test] [--build-only]"
            echo "  --test       Upload to Test PyPI instead of PyPI"
            echo "  --build-only Only build the package (do not upload)"
            echo ""
            echo "To publish to PyPI you need:"
            echo "  1. Account at https://pypi.org (or https://test.pypi.org for --test)"
            echo "  2. API token in ~/.pypirc or TWINE_USERNAME/TWINE_PASSWORD variables"
            echo "  3. Dependencies: pip install build twine"
            exit 0
            ;;
    esac
done

# Check for tools (use venv Python if we are in one)
PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c "import build" 2>/dev/null; then
    echo "Install publish dependencies: pip install build twine"
    echo "Or from the project: pip install -e '.[dev]'"
    exit 1
fi
if ! "$PYTHON" -c "import twine" 2>/dev/null; then
    echo "Missing twine: pip install twine"
    exit 1
fi

# Clean and build
rm -rf dist/
"$PYTHON" -m build

if [ "$BUILD_ONLY" = true ]; then
    echo "Build complete. Artifacts in dist/"
    ls -la dist/
    exit 0
fi

# Upload
if [ -n "$REPO" ]; then
    echo "Uploading to Test PyPI..."
    "$PYTHON" -m twine upload $REPO dist/*
else
    echo "Uploading to PyPI..."
    "$PYTHON" -m twine upload dist/*
fi

echo "Done."
