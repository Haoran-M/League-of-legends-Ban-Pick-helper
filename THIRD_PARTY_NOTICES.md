# Third-party notices

League Draft Assistant includes Python, PySide6/Qt, Shiboken6 and NumPy components in its standalone build. Pandas is used by the source-data preparation workflow. Each retains its original copyright and license; no application license statement overrides upstream terms.

- Python 3.12: Python Software Foundation license and included third-party notices. https://docs.python.org/3.12/license.html
- PySide6 / Shiboken6 6.10.1: LGPL-3.0 / GPL-3.0 / commercial alternatives as published by Qt. This build uses the open-source distribution. https://doc.qt.io/qtforpython-6/licenses.html
- Qt 6.10.1 libraries/plugins: upstream Qt licensing and third-party component notices. https://doc.qt.io/qt-6/licensing.html and https://doc.qt.io/qt-6/licenses-used-in-qt.html
- Source for the matching Qt/PySide release: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.1-src/ and https://download.qt.io/archive/qt/6.10/6.10.1/
- NumPy 2.3.4: BSD-3-Clause plus its bundled third-party notices (including numerical runtime libraries). Included NumPy LICENSE.txt is copied verbatim.
- Pandas 2.3.3: BSD-3-Clause; used by the development aggregation script, not needed in the executable.
- PyInstaller 6.16.0 bootloader: GPL with the upstream distribution exception. https://pyinstaller.org/en/v6.16.0/license.html

The packaged `resources/licenses` folder preserves available upstream license texts. `resources/CC-BY-4.0.txt` covers the separately attributed ChainCC aggregates. DATA_SOURCES.md identifies the data, transformations and Riot portrait attribution. Riot portraits retain Riot's rights and are not covered by the dataset's CC BY license.

The portable folder provides dynamically linked Qt libraries and plugins. The one-file executable extracts the same libraries when run. This local unsigned build has not undergone a public-distribution legal review; retain all notices and review applicable distribution requirements before sharing it publicly.
