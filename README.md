# LIB Explorer — Streamlit demo

Interactive demo of LabFam Individual Biographies (LIB): pick a fictional person and compare
**Before LIB** (panel interview snapshots) with **After LIB** (continuous harmonised spells).
All data are synthetic.

## Run locally

    pip install -r requirements.txt
    streamlit run app.py

## Data

The app reads `data/lib_synthetic_demo.xlsx` (sheets `Wide_LIB`, `Spells_long`,
`Panel_observations`, `Curated_cases`; header in row 3). To update the demo, replace this
file with a corrected version using the same sheet and column names — no code changes needed.

## Deploy

Push this folder to a GitHub repo → share.streamlit.io → "New app" → `app.py`.
Embed on the LIB website with an iframe:

    <iframe src="https://<your-app>.streamlit.app/?embed=true" width="100%" height="1100"></iframe>
