#!/bin/bash

# REQUIRES inkscape and imagemagic

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
pushd "$SCRIPT_DIR"

echo "Generating all SVG renders as PNG"

process-file() {
    # $1 is the name of the plantuml file
    file="$1"
    echo "GENERATING $file"
    filename="${file%.*}"
    inkscape --export-dpi 288 "${filename}.svg" -o "${filename}.png"
    echo "DONE $file"
}

p=0
declare -a processes

for file in *.svg; do
    process-file "$file" &
    processes[$p]=$!
    p=$((p+1))
done

for p in $(seq 0 $((p - 1))); do
    wait ${processes[$p]}
done

echo "✅ SVG images done"

popd
