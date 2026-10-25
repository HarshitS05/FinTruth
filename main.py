from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from analyze import analyze

load_dotenv()

app = FastAPI(title="FinTruth API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    query: str
    tip: str = ""

@app.get("/")
def root():
    return {"status": "online", "product": "FinTruth"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
def analyze_stock(req: AnalyzeRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Enter a stock name or NSE symbol")
    try:
        result = analyze(req.query.strip(), req.tip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"success": True, **result}