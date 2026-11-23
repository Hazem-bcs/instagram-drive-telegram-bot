import base64
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from transfer import decode_job, validate_instagram_url, validate_video_url, ensure_folder, search_existing
from media_urls import parse_video_url
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class JobTests(unittest.TestCase):
    def test_valid_url(self):
        self.assertEqual(validate_instagram_url('https://instagram.com/reel/abc_123/?igsh=abc'),
                         'https://www.instagram.com/reel/abc_123/')

    def test_reject_bad_url(self):
        for url in ['http://instagram.com/reel/id/', 'https://instagram.com.evil.org/reel/id/',
                    'https://instagram.com/stories/someone/44/', 'https://www.instagram.com@evil.org/reel/x/']:
            with self.assertRaises(ValueError):
                validate_instagram_url(url)

    def test_decrypt_job(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        original = {'url': 'https://www.instagram.com/reel/Example1/', 'chat_id': '123456789'}
        payload = json.dumps(original).encode()
        to_b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip('=')
        encrypted = to_b64(iv) + '.' + to_b64(AESGCM(key).encrypt(iv, payload, None))
        self.assertEqual(decode_job(encrypted, to_b64(key)), original)

    def test_refuse_tampered_job(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        to_b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip('=')
        encrypted = AESGCM(key).encrypt(iv, b'{}', None)
        with self.assertRaises(Exception):
            decode_job(to_b64(iv) + '.' + to_b64(encrypted[:-1] + b'X'), to_b64(key))


class SupportedVideoUrlTests(unittest.TestCase):
    def test_supported_video_platform_urls(self):
        samples = {
            "Instagram": ("https://www.instagram.com/reel/abc_123/?igsh=abc",
                          "https://www.instagram.com/reel/abc_123/"),
            "YouTube": ("https://youtu.be/dQw4w9WgXcQ?t=12",
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "Facebook": ("https://www.facebook.com/reel/1234567890/",
                         "https://www.facebook.com/reel/1234567890/"),
            "TikTok": ("https://www.tiktok.com/@creator/video/7345678912345678901?is_copy_url=1",
                       "https://www.tiktok.com/@creator/video/7345678912345678901"),
            "X": ("https://twitter.com/creator/status/1234567890123456?s=20",
                  "https://x.com/i/status/1234567890123456"),
            "Reddit": ("https://www.reddit.com/r/videos/comments/abc123/title/",
                       "https://www.reddit.com/comments/abc123/"),
            "Vimeo": ("https://vimeo.com/12345678?share=copy",
                      "https://vimeo.com/12345678"),
            "Twitch": ("https://clips.twitch.tv/FunnyClip123",
                       "https://clips.twitch.tv/FunnyClip123"),
            "Dailymotion": ("https://www.dailymotion.com/video/x99abc1",
                            "https://www.dailymotion.com/video/x99abc1"),
            "Streamable": ("https://streamable.com/abcd12",
                           "https://streamable.com/abcd12"),
        }
        for platform, (raw, expected) in samples.items():
            with self.subTest(platform=platform):
                self.assertEqual(parse_video_url(raw), (expected, platform))
                self.assertEqual(validate_video_url(raw), expected)

    def test_short_and_video_variants(self):
        urls = {
            "https://youtube.com/shorts/dQw4w9WgXcQ": "YouTube",
            "https://fb.watch/abc123/": "Facebook",
            "https://www.facebook.com/share/r/abcd12/": "Facebook",
            "https://vm.tiktok.com/ZMabcd12/": "TikTok",
            "https://x.com/i/web/status/123456": "X",
            "https://www.twitch.tv/videos/123456": "Twitch",
            "https://www.twitch.tv/creator/clip/GoodClip123": "Twitch",
            "https://v.redd.it/abc123/": "Reddit",
            "https://dai.ly/x99abc1": "Dailymotion",
        }
        for url, platform in urls.items():
            with self.subTest(url=url):
                self.assertEqual(parse_video_url(url)[1], platform)

    def test_reject_unsafe_and_non_video_urls(self):
        rejects = [
            "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/playlist?list=123",
            "https://www.youtube.com/@channel",
            "https://twitter.com/creator",
            "https://www.facebook.com/",
            "https://www.instagram.com/stories/creator/1234/",
            "https://127.0.0.1/reel/abc/",
            "https://www.instagram.com@evil.example/reel/abc",
            "https://www.instagram.com:8443/reel/abc/",
            "https://www.tiktok.com/@x/video/123#fragment",
            "https://www.facebook.com/watch/?v=notanumber",
        ]
        for url in rejects:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_video_url(url)


class DriveApiCallTests(unittest.TestCase):
    def test_folder_list_uses_google_api_page_size_spelling(self):
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "folder-id", "name": "Instagram Videos"}],
        }
        with patch("transfer.ensure_public"):
            folder = ensure_folder(service)
        self.assertEqual(folder["id"], "folder-id")
        kwargs = service.files.return_value.list.call_args.kwargs
        self.assertEqual(kwargs["pageSize"], 10)
        self.assertNotIn("page_size", kwargs)

    def test_existing_file_search_uses_google_api_page_size_spelling(self):
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {"files": []}
        self.assertIsNone(search_existing(service, "folder-id", "test.mp4"))
        kwargs = service.files.return_value.list.call_args.kwargs
        self.assertEqual(kwargs["pageSize"], 10)
        self.assertNotIn("page_size", kwargs)


if __name__ == '__main__':
    unittest.main()
