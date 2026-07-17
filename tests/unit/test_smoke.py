import importlib


def test_package_is_importable() -> None:
    importlib.import_module("pylontech_console")
