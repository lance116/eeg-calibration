#!/usr/bin/env bash
# Fetch the BrainBit macOS SDK (dylib + ObjC headers) from BrainbitLLC/apple_neurosdk2.
# The contents are not redistributed in this repo — run this once after cloning.
set -euo pipefail

REPO="BrainbitLLC/apple_neurosdk2"
REF="${BRAINBIT_REF:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/macos"

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENDOR="${ROOT}/vendor"
HEADERS_DIR="${VENDOR}/Headers"

mkdir -p "${HEADERS_DIR}"

# All NT* headers and the umbrella neurosdk.h. We pull NTUtils.h too even though
# we don't import it — keeping the vendor folder a faithful mirror is more
# useful than saving one HTTP call.
HEADERS=(
  neurosdk.h
  NTBrainBit.h NTBrainBit2.h NTBrainBitBlack.h NTCallibri.h
  NTDeviceFactory.h NTHeadband.h NTHeadphones2.h NTNeuroEEG.h
  NTNeuroEEGSignalProcessing.h NTScanner.h NTSensor.h NTTypes.h NTUtils.h
)

echo "Fetching headers..."
for h in "${HEADERS[@]}"; do
  curl -fsSL "${RAW}/Headers/${h}" -o "${HEADERS_DIR}/${h}"
done

echo "Fetching libneurosdk2.dylib (~9.4 MB)..."
curl -fsSL "${RAW}/libneurosdk2.dylib" -o "${VENDOR}/libneurosdk2.dylib"

# Re-stamp the dylib so the linker's @rpath search finds it from build/eegcli.
echo "Patching install_name to @rpath/libneurosdk2.dylib..."
install_name_tool -id @rpath/libneurosdk2.dylib "${VENDOR}/libneurosdk2.dylib"

echo "Re-signing dylib (required after install_name_tool on Apple Silicon)..."
codesign --force --sign - "${VENDOR}/libneurosdk2.dylib"

echo
echo "OK. Now run: make"
