# Emotion-classifier recording protocol

The classifier is only as good as the contrast in your training data. Use
clearly different inductions for each class and keep conditions consistent
across sessions.

## Suggested 3-class protocol (~18 minutes)

| label    | duration | what to do |
| -------- | -------- | ---------- |
| `happy`  | 3 min    | Headphones on, play a song that genuinely hypes you. Sit upright, eyes open, look at a fixed point. Don't sing along (jaw EMG bleeds into T3/T4). |
| `calm`   | 3 min    | Eyes closed, no music or low ambient. Slow breathing. Don't fall asleep. |
| `sad`    | 3 min    | Headphones on, song that genuinely makes you melancholic. Eyes open, fixed point. |

Repeat the whole block once → six 3-min recordings, ~18 min of EEG.
Each block is its own file so the cross-validator can hold sessions out.

## Recording commands

```bash
# Round 1
./build/eegcli stream --label happy --seconds 180 --out data/happy_1.csv
./build/eegcli stream --label calm  --seconds 180 --out data/calm_1.csv
./build/eegcli stream --label sad   --seconds 180 --out data/sad_1.csv

# Round 2 (do later in the session, or another sitting)
./build/eegcli stream --label happy --seconds 180 --out data/happy_2.csv
./build/eegcli stream --label calm  --seconds 180 --out data/calm_2.csv
./build/eegcli stream --label sad   --seconds 180 --out data/sad_2.csv
```

Run `./build/eegcli resist` between recordings if you adjusted the headband,
to confirm contact is still under 1 MΩ on all four channels.

## Train

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r analyze/requirements.txt
python -m analyze.train data/happy_*.csv data/calm_*.csv data/sad_*.csv \
  --out analyze/model.joblib
```

The trainer holds entire recordings out (`GroupKFold`), so reported accuracy
reflects how well the model generalizes to a new sitting — not how well it
memorizes within one recording.

Realistic targets for 4-channel BrainBit (no frontal coverage):

- 3-class (happy/calm/sad): **45-65%** (chance = 33%)
- Binary arousal (happy vs calm): **70-85%**
- Binary valence (happy vs sad): **60-75%**

If accuracy hugs chance, the most likely culprits are (a) recordings too
similar across labels — try stronger inductions, (b) muscle artifacts from
jaw / brow movement, or (c) the line-noise notch is wrong (`--line-hz 50`
in Europe).

## Predict on a new recording

```bash
./build/eegcli stream --seconds 60 --out data/test.csv
python -m analyze.predict data/test.csv --model analyze/model.joblib
```
