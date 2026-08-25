#!/bin/sh
set -e

TARGET_DIR="${EXTENSIONS_DIR:-/app/extensions}"
TEMP_FILE="/tmp/ext.zip"

# базовый URL для Chrome Web Store
CRX_BASE_URL="https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3D"

# папка|id_или_прямая_ссылка
EXTENSIONS="
ublock|ddkjiahejlhfcafbddmgiahcphecmpfh
bitwarden|nngceckbapebfimnlniiiahkandclblb
gtranslate|aapbdbdomjkkjkaonfhkkikfgjllcleb
grammarly|kbfnbcaeplbcioakkpcpgfkobkghlhen
cookies|edibdbjcniadpccecjdfdjjppcpchdlm
yasearch|laddjijkcfpakbbnnedbhnnciecidncp
clearurls|https://github.com/ClearURLs/Addon/releases/download/1.27.3/ClearURLs.zip
"

echo "starting extension download to: $TARGET_DIR"

for item in $EXTENSIONS; do
    [ -z "$item" ] && continue
    name="${item%%|*}"
    source="${item#*|}"
    dest="$TARGET_DIR/$name"
    # ID или готовая ссылка
    case "$source" in
        http://*|https://*)
            url="$source"
            ;;
        *)
            url="${CRX_BASE_URL}${source}%26uc"
            ;;
    esac

    echo "==> processing: $name"
    mkdir -p "$dest"

    if curl -sSL "$url" -o "$TEMP_FILE"; then
        unzip -qo "$TEMP_FILE" -d "$dest" || true
        rm -f "$TEMP_FILE"
    else
        echo "ERROR: failed to download $name from $url"
    fi
done

echo "extensions downloaded and extracted."