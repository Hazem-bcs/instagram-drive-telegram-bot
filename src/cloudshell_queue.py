"""Interactive, finite queue processing. No daemon or keepalive."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import tempfile
import requests
from media_urls import parse_video_url
from transfer import drive_service, search_existing, upload_video, ensure_public, safe_error_category, MAX_FILE_BYTES


def call(config, path, data=None):
    response = requests.request(
        "GET" if data is None else "POST",
        "https://instagram-drive-telegram-bot.zad-market.workers.dev/queue/" + path,
        headers={"Authorization": "Bearer " + config["queue_access_key"]},
        json=data, timeout=30, allow_redirects=False,
    )
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Unexpected queue HTTP status")
    return response.json()



def process(config, url, service):
    import yt_dlp
    from imageio_ffmpeg import get_ffmpeg_exe
    normalized, platform = parse_video_url(url)
    if platform != "YouTube":
        raise ValueError("Only YouTube")
    video_id = normalized.split("v=")[-1]
    name = f"YouTube_{video_id}.mp4"
    folder_id = config["drive_folder_id"]
    existing = search_existing(service, folder_id, name)
    if existing:
        ensure_public(service, existing["id"])
        return existing["id"]
    with tempfile.TemporaryDirectory() as folder:
        opts = {
            "ffmpeg_location": get_ffmpeg_exe(),
            "format": "bv[ext=mp4][height<=360]+ba[ext=m4a][language^=ar]/bv[ext=mp4][height<=360]+ba[ext=m4a]/b[ext=mp4][height<=360]",
            "merge_output_format": "mp4", "noplaylist":True, "playlist_items":"1",
            "outtmpl":str(Path(folder)/"sample.%(ext)s"),
            "max_filesize":MAX_FILE_BYTES, "socket_timeout":20, "retries":0,
            "fragment_retries":0, "quiet":True, "noprogress":True,
            "match_filter":yt_dlp.utils.match_filter_func("!is_live"),
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(normalized, download=True)
        path = Path(folder)/"sample.mp4"
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
            raise ValueError("Missing or oversized MP4")
        return upload_video(service,path,name,folder_id)["id"]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--test-url", help="Explicit authorized single-video transfer test, without claiming a queue job")
    parser.add_argument("--check",action="store_true",help="Only check authentication and existing Drive folder")
    args=parser.parse_args()
    folder=Path.home()/".config/video-archive"
    config_path=folder/"pairing.json"
    if not config_path.is_file():
        print("Missing private pairing file: "+str(config_path))
        return 1
    config=json.loads(config_path.read_text())
    os.environ["GOOGLE_OAUTH_JSON"]=json.dumps(config["google_oauth"])
    try:
        with (folder/"processing.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            service=drive_service()
            service.files().get(fileId=config["drive_folder_id"],fields="id,name").execute()
            if args.check:
                print("Drive folder access verified.")
                print("Queue access verified. Pending:",len(call(config,"jobs")["jobs"]))
                return 0
            if args.test_url:
                file_id=process(config,args.test_url,service)
                print("Saved: https://drive.google.com/file/d/"+file_id+"/view")
                return 0
            pending=call(config,"jobs")["jobs"]
            print("Pending videos:",len(pending))
            failures=0
            for item in pending:
                try:
                    job=call(config,"claim",item)
                except requests.HTTPError as exc:
                    if exc.response.status_code==409:
                        continue
                    raise
                lease={"video_id":job["video_id"],"lease":job["lease"]}
                try:
                    file_id=process(config,job["url"],service)
                    outcome=call(config,"complete",{**lease,"drive_id":file_id})
                    print("Saved: https://drive.google.com/file/d/"+file_id+"/view")
                    if not outcome.get("notified"):
                        print("Telegram notification failed; the file is saved.")
                except Exception as exc:
                    failures+=1
                    print("Job failed:",safe_error_category(exc))
                    try: call(config,"release",lease)
                    except Exception: print("Lease will expire automatically.")
            return 1 if failures else 0
    except Exception as exc:
        print("Processing stopped:",type(exc).__name__,safe_error_category(exc))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
