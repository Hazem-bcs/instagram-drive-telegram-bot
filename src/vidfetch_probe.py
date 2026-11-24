import os, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def request(path, data=None):
    req = Request("https://api.vidfetch.dev/v1/"+path,
                  headers={"Authorization":"Bearer "+os.environ["VIDFETCH_API_KEY"],"Content-Type":"application/json"},
                  data=json.dumps(data).encode() if data is not None else None)
    try:
        with urlopen(req,timeout=30) as r:
            return r.status,json.load(r)
    except HTTPError as e:
        return e.code,{}

for path, data in [
    ("usage", None),
    ("info", {"url":"https://www.youtube.com/watch?v=YE7VzlLtp-4"}),
    ("info", {"url":"https://www.youtube.com/watch?v=nYYitW53CXI"}),
]:
    try:
        status, result = request(path,data)
        print("PROBE",path,status,"response keys:",sorted(result.keys()),flush=True)
        for k in ("duration","duration_seconds","downloadable","available","plan","remaining_gb","quota_remaining_bytes"):
            if isinstance(result.get(k),(int,float,bool,str)):
                print(k, result[k], flush=True)
    except Exception as e:
        print("PROBE_FAILED",type(e).__name__,flush=True)
