import unittest
from downloader.tiktok import TikTokDownloader
from downloader.instagram import InstagramDownloader
from downloader.manager import MediaManager


class TestParsers(unittest.TestCase):
    def setUp(self):
        self.manager = MediaManager()
        self.tiktok = TikTokDownloader()
        self.instagram = InstagramDownloader()

    def test_tiktok_urls(self):
        urls = [
            ("https://www.tiktok.com/@username/video/7123456789012345678", True),
            ("https://vt.tiktok.com/ZS2xyz123/", True),
            ("https://vm.tiktok.com/ZM8abc789/", True),
            ("https://www.tiktok.com/@user/photo/7987654321098765432", True),
            ("https://www.tiktok.com/@user/story/7987654321098765432", True),
            ("Check this out: https://vt.tiktok.com/ZS2xyz123/ so cool", True),
            ("https://example.com/not-tiktok", False),
        ]
        for text, expected in urls:
            extracted = self.tiktok.extract_url(text)
            self.assertEqual(bool(extracted), expected, f"Failed for text: {text}")

    def test_instagram_urls(self):
        urls = [
            ("https://www.instagram.com/reel/C3abcXYZ_12/?igsh=MzRlODBiNWFlZA==", True),
            ("https://instagram.com/p/C99xyzABCDE/", True),
            ("https://www.instagram.com/stories/username/3456789012345678901/", True),
            ("https://www.instagram.com/share/reel/123456", True),
            ("Look at this: https://instagram.com/reel/C3abcXYZ_12/ hilarious", True),
            ("https://google.com", False),
        ]
        for text, expected in urls:
            extracted = self.instagram.extract_url(text)
            self.assertEqual(bool(extracted), expected, f"Failed for text: {text}")

    def test_manager_detection(self):
        res_tt = self.manager.find_supported_url("Here is tiktok https://vt.tiktok.com/ZS2xyz123/")
        self.assertIsNotNone(res_tt)
        self.assertEqual(res_tt[0], "TikTok")

        res_ig = self.manager.find_supported_url("Here is IG https://www.instagram.com/reel/C3abcXYZ_12/")
        self.assertIsNotNone(res_ig)
        self.assertEqual(res_ig[0], "Instagram")

        res_none = self.manager.find_supported_url("Just normal chat message")
        self.assertIsNone(res_none)


if __name__ == "__main__":
    unittest.main()
