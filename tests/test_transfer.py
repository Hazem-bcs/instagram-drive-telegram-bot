import base64
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from transfer import decode_job, validate_instagram_url
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


if __name__ == '__main__':
    unittest.main()
