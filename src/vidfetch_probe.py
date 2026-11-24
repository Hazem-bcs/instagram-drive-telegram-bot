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
        body=e.read(8192).decode(errors="replace").lower()
        print("HTTP_ERROR",e.code,"content_type",e.headers.get("Content-Type"),"server",e.headers.get("Server"),flush=True)
        for label,needle in [("browser_security","error code: 1010"),("challenge","challenge-platform"),("blocked","access denied"),("invalid_key","invalid_api_key"),("forbidden","forbidden"),("unauthorized","unauthorized"),("quota","quota_exceeded"),("region","region"),("cloudflare","cloudflare")]:
            if needle in body:
                print("ERROR_CATEGORY",label,flush=True)
        return e.code,{}

for path, data in [
    ("usage", None),
]:
    try:
        status, result = request(path,data)
        print("PROBE",path,status,"response keys:",sorted(result.keys()),flush=True)
        for k in ("duration","duration_seconds","downloadable","available","plan","remaining_gb","quota_remaining_bytes"):
            if isinstance(result.get(k),(int,float,bool,str)):
                print(k, result[k], flush=True)
    except Exception as e:
        print("PROBE_FAILED",type(e).__name__,flush=True)
