# Android third-party notices

This APK uses the shared League Draft Python domain model, SQLite repository and statistical engine with a native Android interface. It does not contain the Windows PySide6/Qt interface, pandas or NumPy. A standard-library linear percentile fallback preserves the desktop engine's percentile behavior.

Runtime components retain their upstream copyrights and licenses:

- Chaquopy 17.2.0: MIT. https://github.com/chaquo/chaquopy and the included licenses/Chaquopy.txt.
- CPython 3.12: Python Software Foundation license and bundled third-party notices. See licenses/Python-3.12.txt and https://docs.python.org/3.12/license.html.
- CPython's bundled SQLite, compression, SSL and foreign-function support retain their upstream terms. SQLite is public domain; OpenSSL uses the Apache 2.0 license; libffi uses an MIT-style license; zlib and bzip2 have their own permissive terms. The Python notices and upstream Chaquopy source identify these components.
- Android platform APIs are provided by the device. AndroidX Test and UI Automator are used only by the separate test APK, not the distributable app.

The historical aggregate dataset is separately attributed to ChainCC under its published CC BY 4.0 license. See DATA_SOURCES.md and CC-BY-4.0.txt. Riot champion names, portraits and metadata retain Riot Games' rights and are not relicensed as CC BY by this app.

League Draft Assistant is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

The APK is signed with a local development certificate for personal installation and testing. It is not published on Google Play. No Internet, account, overlay or broad storage permission is requested. Initial scope remains offline simulation and historical comparisons.
