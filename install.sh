#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME/.local/bin/cctoken"

mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/cctoken/cctoken.py" "$TARGET"
chmod +x "$SCRIPT_DIR/cctoken/cctoken.py"

echo "Installed: $TARGET"
echo "Make sure ~/.local/bin is in your PATH."
echo "  Add to ~/.zshrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
