# BarrelLabs SwingAI

AI-powered baseball swing analysis — built for better swings.

Players upload a phone video of their swing, get a biomechanics breakdown, an MLB hitter comparison, similarity score, top fixes, and personalized drills.

## Stack

- **Frontend / runtime**: Streamlit
- **Pose detection**: MediaPipe + OpenCV
- **Auth + DB**: Supabase
- **Payments**: Stripe
- **Reports**: ReportLab (PDF)

## Run locally

```bash
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Add your secrets at `.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example` for shape). Then:

```bash
streamlit run app.py
```

## Deploy (Streamlit Cloud)

1. Push this repo to GitHub
2. Sign into [share.streamlit.io](https://share.streamlit.io) with GitHub
3. Click **New app** → pick the repo → main file: `app.py`
4. In **Advanced settings → Secrets**, paste the contents of your local `.streamlit/secrets.toml`
5. Deploy
