import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

import downloader
import updater


class FormatSelectionTests(unittest.TestCase):
    def test_prefers_highest_video_at_or_below_target(self):
        info = {
            "formats": [
                {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none", "tbr": 5000},
                {"format_id": "299", "height": 1080, "vcodec": "avc1", "acodec": "none", "fps": 60, "tbr": 4500},
                {"format_id": "315", "height": 2160, "vcodec": "av01", "acodec": "none", "tbr": 9000},
                {"format_id": "251", "height": None, "vcodec": "none", "acodec": "opus", "abr": 160},
            ]
        }
        selector, height = downloader._select_format(info, 1080)
        self.assertEqual(selector, "299+251")
        self.assertEqual(height, 1080)

    def test_falls_back_to_highest_available_video(self):
        info = {
            "formats": [
                {"format_id": "22", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "tbr": 2000},
                {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "tbr": 800},
            ]
        }
        selector, height = downloader._select_format(info, 1080)
        self.assertEqual(selector, "22")
        self.assertEqual(height, 720)

    def test_prefers_combined_format_for_fallback_clients(self):
        info = {
            "formats": [
                {"format_id": "136", "height": 720, "vcodec": "avc1", "acodec": "none", "tbr": 1800},
                {"format_id": "140", "height": None, "vcodec": "none", "acodec": "mp4a", "abr": 130},
                {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "tbr": 600},
            ]
        }
        selector, height = downloader._select_format(info, 1080, prefer_combined=True)
        self.assertEqual(selector, "18")
        self.assertEqual(height, 360)

    def test_raises_when_no_media_format_exists(self):
        with self.assertRaisesRegex(ValueError, "No compatible"):
            downloader._select_format({"formats": [{"format_id": "251", "vcodec": "none", "acodec": "opus"}]}, 1080)

    def test_image_only_diagnostic_is_a_format_failure(self):
        self.assertTrue(downloader._is_format_error("Only images are available for download"))


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_configured_runtime_directory_is_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = os.path.join(temp_dir, "deno.exe")
            open(runtime, "wb").close()
            with mock.patch.dict(os.environ, {"YTDLP_JS_RUNTIME": temp_dir}, clear=False):
                self.assertEqual(downloader._find_js_runtime(), runtime)


class UpdaterTests(unittest.TestCase):
    def test_nightly_repository_uses_expected_download_endpoint(self):
        self.assertEqual(
            updater._repository_download_url(updater.NIGHTLY_REPOSITORY),
            "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp",
        )

    def test_source_update_uses_pre_release_flag_for_nightly(self):
        completed = mock.Mock(stdout="nightly installed", stderr="")
        with mock.patch.object(updater.subprocess, "run", return_value=completed) as run, \
             mock.patch.object(updater, "_source_dependencies_ready", return_value=True):
            success, details = updater._run_source_pip_update(pre_release=True)

        self.assertTrue(success)
        self.assertIn("nightly installed", details)
        command = run.call_args.args[0]
        self.assertIn("--pre", command)
        self.assertEqual(command[-1], "yt-dlp[default]")

    def test_valid_zipapp_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "yt-dlp.zip")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("yt_dlp/version.py", "__version__ = '2026.01.01'\n")
            self.assertTrue(updater._valid_zipapp(path))
            self.assertEqual(updater._read_zipapp_version(path), "2026.01.01")

    def test_corrupt_zipapp_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "yt-dlp.zip")
            with open(path, "wb") as file:
                file.write(b"not a zipapp")
            self.assertFalse(updater._valid_zipapp(path))


class HistoryTests(unittest.TestCase):
    def test_youtube_aliases_share_one_identity(self):
        urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123?si=tracking",
            "https://www.youtube.com/shorts/abc123?list=playlist",
            "https://www.youtube.com/embed/abc123",
        ]
        identities = {downloader.get_download_identity(url) for url in urls}
        self.assertEqual(identities, {"youtube:abc123"})

    def test_history_matches_legacy_url_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "download_history.json")
            with open(history_path, "w", encoding="utf-8") as file:
                file.write('[{"title": "Legacy", "url": "https://youtu.be/abc123"}]')
            record = downloader.get_download_history_record(
                "https://www.youtube.com/watch?v=abc123",
                temp_dir,
            )
            self.assertEqual(record["title"], "Legacy")

    def test_completed_history_is_atomic_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            info = {
                "id": "abc123",
                "extractor_key": "Youtube",
                "webpage_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Example",
                "uploader": "Tester",
            }
            self.assertTrue(downloader.record_completed_download("ignored", temp_dir, info))
            self.assertFalse(downloader.record_completed_download("ignored", temp_dir, info))
            with open(os.path.join(temp_dir, "download_history.json"), encoding="utf-8") as file:
                records = json.load(file)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "completed")

    def test_corrupt_history_is_preserved_and_does_not_block_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "download_history.json")
            with open(history_path, "w", encoding="utf-8") as file:
                file.write("not json")
            self.assertIsNone(
                downloader.get_download_history_record(
                    "https://example.com/video",
                    temp_dir,
                )
            )
            self.assertTrue(os.path.exists(history_path + ".invalid"))


class DownloaderFlowTests(unittest.TestCase):
    def test_download_inspects_formats_before_download_and_uses_final_filepath(self):
        class FakeYoutubeDL:
            calls = []

            def __init__(self, options):
                self.options = options
                FakeYoutubeDL.calls.append(options)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def extract_info(self, url, download=False):
                if not download:
                    return {
                        "title": "Example",
                        "uploader": "Tester",
                        "webpage_url": url,
                        "formats": [
                            {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none"},
                            {"format_id": "251", "height": None, "vcodec": "none", "acodec": "opus", "abr": 160},
                        ],
                    }
                filepath = self.options["test_filepath"]
                with open(filepath, "wb") as file:
                    file.write(b"merged")
                return {
                    "title": "Example",
                    "uploader": "Tester",
                    "webpage_url": url,
                    "filepath": filepath,
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            ffmpeg = os.path.join(temp_dir, "ffmpeg.exe")
            open(ffmpeg, "wb").close()
            final_file = os.path.join(temp_dir, "merged.mp4")
            with mock.patch.object(downloader, "FFMPEG_PATH", ffmpeg), \
                 mock.patch.object(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL), \
                 mock.patch.object(downloader, "run_handbrake_conversion", return_value=True):
                original_init = FakeYoutubeDL.__init__

                def init_with_test_filepath(self, options):
                    options = dict(options)
                    options["test_filepath"] = final_file
                    original_init(self, options)

                with mock.patch.object(FakeYoutubeDL, "__init__", init_with_test_filepath):
                    result = downloader.download_youtube_video(
                        "https://example.com/video",
                        temp_dir,
                        resolution="1080p",
                    )

            self.assertTrue(result)
            self.assertTrue(any(call.get("format") == "137+251" for call in FakeYoutubeDL.calls))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "download_history.json")))


class ConversionHistoryTests(unittest.TestCase):
    def test_failed_conversion_does_not_create_history(self):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def extract_info(self, url, download=False):
                if not download:
                    return {
                        "title": "Example",
                        "uploader": "Tester",
                        "webpage_url": url,
                        "formats": [
                            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a"},
                        ],
                    }
                filepath = self.options["test_filepath"]
                with open(filepath, "wb") as file:
                    file.write(b"merged")
                return {"title": "Example", "uploader": "Tester", "webpage_url": url, "filepath": filepath}

        with tempfile.TemporaryDirectory() as temp_dir:
            ffmpeg = os.path.join(temp_dir, "ffmpeg.exe")
            open(ffmpeg, "wb").close()
            final_file = os.path.join(temp_dir, "merged.mp4")
            original_init = FakeYoutubeDL.__init__

            def init_with_test_filepath(self, options):
                options = dict(options)
                options["test_filepath"] = final_file
                original_init(self, options)

            with mock.patch.object(downloader, "FFMPEG_PATH", ffmpeg), \
                 mock.patch.object(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL), \
                 mock.patch.object(FakeYoutubeDL, "__init__", init_with_test_filepath), \
                 mock.patch.object(downloader, "run_handbrake_conversion", return_value=False):
                result = downloader.download_youtube_video("https://example.com/video", temp_dir)

            self.assertFalse(result)
            self.assertFalse(os.path.exists(os.path.join(temp_dir, "download_history.json")))


class HandBrakeTests(unittest.TestCase):
    def test_handbrake_output_is_decoded_and_source_removed(self):
        class FakeProcess:
            def __init__(self, command, **kwargs):
                self.command = command
                self.stdout = io.StringIO("Encoding: task 100.00 %\n")

            def wait(self, timeout=None):
                output_path = self.command[self.command.index("-o") + 1]
                with open(output_path, "wb") as output:
                    output.write(b"converted")
                return 0

            def terminate(self):
                return None

            def kill(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.webm")
            with open(source, "wb") as file:
                file.write(b"source")
            preset = os.path.join(temp_dir, "resolve_preset.json")
            handbrake = os.path.join(temp_dir, "HandBrakeCLI.exe")
            with open(preset, "w", encoding="utf-8") as file:
                file.write("{}")
            with open(handbrake, "wb") as file:
                file.write(b"binary")

            with mock.patch.object(downloader, "HANDBRAKE_CLI_PATH", handbrake), \
                 mock.patch.object(downloader, "HANDBRAKE_PRESET_FILE", preset), \
                 mock.patch.object(downloader.subprocess, "Popen", FakeProcess):
                result = downloader.run_handbrake_conversion(source, temp_dir, use_nvenc=False)

            self.assertTrue(result)
            self.assertFalse(os.path.exists(source))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "source_Handbraked.mp4")))


if __name__ == "__main__":
    unittest.main()
