import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication

from league_draft.domain.roster import load_roster


@pytest.fixture
def roster():
    return load_roster()[0]


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication([])
    yield application
