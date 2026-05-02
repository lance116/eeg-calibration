# eeg-calibration

macOS CLI for testing and calibrating a BrainBit EEG headband against the
official BrainBit SDK 2 (`libneurosdk2.dylib`, Swift via an ObjC bridging
header).

The BrainBit headband has 4 dry electrodes — **O1, O2, T3, T4** — sampled at
**250 Hz**. SDK reference: <https://sdk.brainbit.com/sdk2_macos_install/>.

## One-time setup

```bash
./setup.sh   # downloads libneurosdk2.dylib + headers into ./vendor
make         # compiles ./build/eegcli
```

`setup.sh` pulls the SDK from
[BrainbitLLC/apple_neurosdk2](https://github.com/BrainbitLLC/apple_neurosdk2)
and patches the dylib's install name to `@rpath/...` so the binary in
`./build/` can find it at runtime. It also re-codesigns the dylib (required on
Apple Silicon after `install_name_tool`).

The first `eegcli` run will trigger a macOS Bluetooth permission prompt.
Approve it. If you missed it: System Settings → Privacy & Security → Bluetooth.

## Usage

```bash
./build/eegcli scan                         # discover headbands (5 s)
./build/eegcli resist                       # live electrode contact check
./build/eegcli stream --seconds 30 --out data/session.csv
./build/eegcli calibrate --out data/baseline.csv
```

All subcommands accept `--serial <SerialNumber>` to target a specific device
when more than one is in range; otherwise the first found wins.

## Layout

```
Makefile              # builds ./build/eegcli with swiftc
setup.sh              # vendors libneurosdk2.dylib + Headers
Info.plist            # embedded into the binary for Bluetooth usage prompt
Sources/
  shim.h              # ObjC bridging header for the SDK
  main.swift          # subcommand dispatch
  Device.swift        # scan + connect helper
  Scan.swift / Resistance.swift / Stream.swift / Calibrate.swift
vendor/               # populated by setup.sh (gitignored)
data/                 # CSV recordings (gitignored)
```
