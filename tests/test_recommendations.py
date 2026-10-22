import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.services.recommendations import recommendations
def test_personalized_rules():
    x={"FAVC":"yes","FCVC":1,"CAEC":"Frequently","CH2O":1,"FAF":0,"TUE":2}
    r=recommendations(x); codes={a["code"] for a in r}
    assert {"balanced-meals","vegetables","snacks","hydration","movement","screen-breaks"}.issubset(codes)
    assert all(a["reason"] and a["steps"] and a["source_url"].startswith("https://") for a in r)
def test_default_rule():
    x={"FAVC":"no","FCVC":3,"CAEC":"Sometimes","CH2O":3,"FAF":3,"TUE":0}
    assert recommendations(x)[0]["code"] == "maintain-habits"
