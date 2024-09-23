#!/usr/bin/env bash

set -e
set -x

TARGET_DIR=$(readlink -f "$1")
SCRIPT_DIR=$(readlink -f "$(dirname "$0")")
CODE_DIR=$(readlink -f "$SCRIPT_DIR/..")
REQUIREMENTS_FILE="$CODE_DIR/requirements-circuitpython.txt"
BOOT_OUT_FILE="$TARGET_DIR/boot_out.txt"
BOOT_OUT_TEMPLATE="$SCRIPT_DIR/boot_out_template.txt"

DIST_LANGUAGE=zh_CN
if [[ -n "$2" ]]; then
    DIST_LANGUAGE="$2"
fi

# CPY_REQUIREMENTS=$(awk '/^[a-z].*/ { printf "%s ", $0 }' "$CODE_DIR/requirements-circuitpython.txt")
[ -d "$TARGET_DIR" ] || mkdir -p "$TARGET_DIR"

printf "Copy code files\n"
for f in boot.py code.py safemode.py settings.toml lib requirements-circuitpython.txt; do
    rsync -r "$CODE_DIR/$f" "$TARGET_DIR/"
done

printf "Install requirements\n"
if [ -f "$BOOT_OUT_FILE" ]; then
    circup --path "$TARGET_DIR" --timeout 10 install -r "$REQUIREMENTS_FILE"
else
    cp "$BOOT_OUT_TEMPLATE" "$BOOT_OUT_FILE"
    circup --path "$TARGET_DIR" --timeout 10 install -r "$REQUIREMENTS_FILE"
    rm "$BOOT_OUT_FILE"
fi

printf "Copy DIST files (doc, examples, etc)\n"
# readme
DIST_README_NAME=$(awk -F: '/^'"$DIST_LANGUAGE"'/ { printf "%s", $2 }' "$CODE_DIR/README_dist/dist-names.txt")
md2html -o "$TARGET_DIR/$DIST_README_NAME.html" -t "$DIST_README_NAME" "$CODE_DIR/README_dist/$DIST_LANGUAGE.md" 
rsync -r "$CODE_DIR/README_dist/$DIST_LANGUAGE.md" "$TARGET_DIR/$DIST_README_NAME.md" 
# examples
DIST_EXAMPLES_NAME=$(awk -F: '/^'"$DIST_LANGUAGE"'/ { printf "%s", $2 }' "$CODE_DIR/keymap-examples/dist-names.txt")
rsync -r "$CODE_DIR/keymap-examples/$DIST_LANGUAGE/" "$TARGET_DIR/$DIST_EXAMPLES_NAME/"
# doc
DIST_DOC_NAME=$(awk -F: '/^'"$DIST_LANGUAGE"'/ { printf "%s", $2 }' "$CODE_DIR/doc/dist-names.txt")
rsync -r "$CODE_DIR/doc/$DIST_LANGUAGE/" "$TARGET_DIR/$DIST_DOC_NAME/"

printf "Patching files\n"
sed -i "s/^keypad.debug = True/#keypad.debug = True/g" "$TARGET_DIR/code.py"

printf "Creating misc files\n"
cat << EOF > "$TARGET_DIR/lock_usb_drive.txt"
Delete this file to disable write protection of the emulated USB drive.
删除这个文件来禁用模拟U盘写保护。
EOF
