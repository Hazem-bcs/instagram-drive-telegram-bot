"""Validated URL normalizer for supported video platforms.

Only permit known public-video URL patterns and exact platform hostnames.
Never pass arbitrary URLs from Telegram to yt-dlp (or GitHub Actions).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, parse_qs

HOSTS = {
    "Instagram": {"instagram.com", "www.instagram.com", "m.instagram.com"},
    "YouTube": {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"},
    "Facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com", "fb.watch"},
    "TikTok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "X": {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"},
    "Reddit": {"reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "redd.it", "v.redd.it"},
    "Vimeo": {"vimeo.com", "www.vimeo.com", "player.vimeo.com"},
    "Twitch": {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"},
    "Dailymotion": {"dailymotion.com", "www.dailymotion.com", "dai.ly"},
    "Streamable": {"streamable.com", "www.streamable.com"},
}

def _match(pattern: str, path: str, flags: int = 0):
    return re.fullmatch(pattern, path, flags=flags)

def parse_video_url(raw: str) -> tuple[str, str]:
    """Return (safe canonical video URL, platform), raising ValueError if unsupported."""
    if not isinstance(raw, str) or len(raw) > 2048:
        raise ValueError("Invalid video URL")
    try:
        p = urlsplit(raw)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or p.username or p.password or p.port or p.fragment:
            raise ValueError("Unexpected URL components")
    except ValueError:
        raise ValueError("Invalid or unsafe URL") from None
    platform = next((name for name, hosts in HOSTS.items() if host in hosts), None)
    if not platform:
        raise ValueError("Unsupported video platform")
    path = p.path
    m = None

    if platform == "Instagram":
        m = _match(r"/(reel|reels|p|tv)/([A-Za-z0-9_-]+)/?", path, re.I)
        if m:
            return f"https://www.instagram.com/{m.group(1).lower()}/{m.group(2)}/", platform

    elif platform == "YouTube":
        video_id = None
        if host == "youtu.be":
            m = _match(r"/([A-Za-z0-9_-]{11})/?", path)
            video_id = m.group(1) if m else None
        elif path == "/watch":
            video_id = parse_qs(p.query).get("v", [None])[0]
        else:
            m = _match(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})/?", path)
            video_id = m.group(1) if m else None
        if video_id and _match(r"[A-Za-z0-9_-]{11}", video_id):
            return f"https://www.youtube.com/watch?v={video_id}", platform

    elif platform == "Facebook":
        if host == "fb.watch":
            m = _match(r"/([A-Za-z0-9_-]+)/?", path)
            if m:
                return f"https://fb.watch/{m.group(1)}/", platform
        elif path == "/watch":
            video_id = parse_qs(p.query).get("v", [None])[0]
            if video_id and video_id.isascii() and video_id.isdecimal():
                return f"https://www.facebook.com/watch/?v={video_id}", platform
        else:
            m = (_match(r"/(?:reel|videos)/(\d+)/?", path, re.I)
                 or _match(r"/[A-Za-z0-9._-]+/videos/(\d+)/?", path, re.I))
            if m:
                return f"https://www.facebook.com/reel/{m.group(1)}/", platform
            m = _match(r"/share/(r|v)/([A-Za-z0-9_-]+)/?", path, re.I)
            if m:
                return f"https://www.facebook.com/share/{m.group(1).lower()}/{m.group(2)}/", platform

    elif platform == "TikTok":
        if host in {"vm.tiktok.com", "vt.tiktok.com"}:
            m = _match(r"/([A-Za-z0-9_-]+)/?", path)
            if m:
                return f"https://{host}/{m.group(1)}/", platform
        else:
            m = _match(r"/@([A-Za-z0-9._-]+)/video/(\d+)/?", path)
            if m:
                return f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}", platform
            m = _match(r"/t/([A-Za-z0-9_-]+)/?", path)
            if m:
                return f"https://www.tiktok.com/t/{m.group(1)}/", platform

    elif platform == "X":
        m = (_match(r"/(?:[A-Za-z0-9_]+|i)/status/(\d+)/?", path, re.I)
             or _match(r"/i/web/status/(\d+)/?", path, re.I))
        if m:
            return f"https://x.com/i/status/{m.group(1)}", platform

    elif platform == "Reddit":
        if host in {"redd.it", "v.redd.it"}:
            m = _match(r"/([A-Za-z0-9]+)/?", path)
            if m:
                return f"https://{host}/{m.group(1)}/", platform
        else:
            m = _match(r"/(?:r/[A-Za-z0-9_]+/)?comments/([A-Za-z0-9]+)(?:/[^?#]*)?/?", path)
            if m:
                return f"https://www.reddit.com/comments/{m.group(1)}/", platform

    elif platform == "Vimeo":
        m = (_match(r"/(\d+)/?", path)
             or _match(r"/(?:channels/[A-Za-z0-9_-]+|groups/[A-Za-z0-9_-]+/videos|video|album/\d+/video)/(\d+)/?", path))
        if m:
            return f"https://vimeo.com/{m.group(1)}", platform

    elif platform == "Twitch":
        if host == "clips.twitch.tv":
            m = _match(r"/([A-Za-z0-9_-]+)/?", path)
            if m:
                return f"https://clips.twitch.tv/{m.group(1)}", platform
        else:
            m = _match(r"/videos/(\d+)/?", path)
            if m:
                return f"https://www.twitch.tv/videos/{m.group(1)}", platform
            m = _match(r"/([A-Za-z0-9_]+)/clip/([A-Za-z0-9_-]+)/?", path, re.I)
            if m:
                return f"https://www.twitch.tv/{m.group(1)}/clip/{m.group(2)}", platform

    elif platform == "Dailymotion":
        m = _match(r"/(?:video/)?([A-Za-z0-9]+)/?", path)
        if m:
            return f"https://www.dailymotion.com/video/{m.group(1)}", platform

    elif platform == "Streamable":
        m = _match(r"/([A-Za-z0-9]+)/?", path)
        if m:
            return f"https://streamable.com/{m.group(1)}", platform

    raise ValueError("Unsupported video URL path")
