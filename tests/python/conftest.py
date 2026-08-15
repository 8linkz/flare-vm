"""Pytest configuration for the FLARE-VM Python tests.

Adds the ``virtualbox`` directory to ``sys.path`` so the scripts under test can be imported by name
(``import vboxcommon``). The scripts talk to VBoxManage via subprocess; tests must mock that layer and
never invoke real VirtualBox.
"""

import os
import sys

VIRTUALBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "virtualbox"))
if VIRTUALBOX_DIR not in sys.path:
    sys.path.insert(0, VIRTUALBOX_DIR)

import importlib.util  # noqa: E402

import pytest  # noqa: E402


def _load_script(module_name, filename):
    """Load a dash-named virtualbox script as an importable module (its main() is guarded by __main__)."""
    path = os.path.join(VIRTUALBOX_DIR, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_snapshots():
    return _load_script("vbox_clean_snapshots", "vbox-clean-snapshots.py")
