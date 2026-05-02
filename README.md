# eeg-calibration

Scripts for testing and calibrating a BrainBit EEG headband on macOS using the
official BrainBit SDK 2 (`pyneurosdk2`).

The BrainBit headband has 4 dry electrodes — **O1, O2, T3, T4** — sampled at
**250 Hz**. SDK reference: <https://sdk.brainbit.com/sdk2_scanner/>.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### macOS Bluetooth permission

The first time you run any of these scripts, macOS will prompt to let your
terminal use Bluetooth. Approve it, otherwise scanning silently returns nothing.
If you missed the prompt: System Settings → Privacy & Security → Bluetooth →
enable for Terminal / iTerm / your IDE.

## Usage

All commands assume the venv is active.

```bash
# 1. Discover nearby headbands (5 s scan)
python -m src.scan

# 2. Check electrode contact quality (lower kΩ is better; aim < 2 MΩ)
python -m src.resistance

# 3. Stream signal to stdout / CSV
python -m src.stream --seconds 30 --out data/session.csv

# 4. Full calibration: contact check + 60 s eyes-open / 60 s eyes-closed baseline
python -m src.calibrate --out data/baseline.csv
```

By default each script picks the first headband it finds. Pass `--serial
<SerialNumber>` to target a specific device when multiple are nearby.

## Layout

```
src/
  scan.py         discover headbands
  resistance.py   electrode contact check
  stream.py       record signal to CSV
  calibrate.py    eyes-open / eyes-closed baseline session
  _device.py      shared scan-and-connect helper
```
