# FinTruth
Plain-English risk checks on Indian stocks, plus a scam scan for stock tips.

## Run
pip install -r requirements.txt
copy .env.example .env   (then add your GROQ_API_KEY)
uvicorn main:app --reload
Open FinTruth.html in your browser (backend runs on http://127.0.0.1:8000)