"""Configuration regressions without database, network or torch."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote_plus, urlsplit

CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"


def load_settings(env):
    spec = importlib.util.spec_from_file_location("config_under_test", CONFIG_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv") as loader:
        spec.loader.exec_module(module)
    return module, loader


class ConfigTests(unittest.TestCase):
    def test_defaults_have_no_credentials_or_gateway(self):
        module, _ = load_settings({})
        self.assertEqual(module.settings.DB_PASSWORD, "")
        self.assertEqual(module.settings.TUSHARE_TOKEN, "")
        self.assertEqual(module.settings.TUSHARE_API_URL, "")

    def test_environment_overrides(self):
        module, _ = load_settings({"DB_HOST": "db.example", "DB_PORT": "3307",
                                   "DB_NAME": "research", "TUSHARE_TOKEN": "test-only"})
        self.assertEqual(module.settings.DB_HOST, "db.example")
        self.assertEqual(module.settings.DB_PORT, 3307)
        self.assertEqual(module.settings.DB_NAME, "research")
        self.assertEqual(module.settings.TUSHARE_TOKEN, "test-only")

    def test_password_special_characters_are_encoded(self):
        password = "test@:/#?+ value"
        module, _ = load_settings({"DB_USER": "test@user", "DB_PASSWORD": password})
        parsed = urlsplit(module.settings.DATABASE_URL)
        self.assertEqual(unquote_plus(parsed.username), "test@user")
        self.assertEqual(unquote_plus(parsed.password), password)
        self.assertEqual(parsed.hostname, "127.0.0.1")

    def test_dotenv_uses_repository_root(self):
        _, loader = load_settings({})
        loader.assert_called_once_with(CONFIG_PATH.parents[2] / ".env")


if __name__ == "__main__":
    unittest.main()
