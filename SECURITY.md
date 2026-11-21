# Security policy

This early application runs offline with local imports and persistence. There is no telemetry/account service or game-client connection; Android requests no Internet permission. Setup/build scripts download dependencies and tools.

Use GitHub **Security → Report a vulnerability** if available, or a maintainer contact listed on their GitHub profile. Do not post secrets, private drafts, signing keys or sensitive vulnerability details in public issues. Public issues are appropriate for ordinary nonsensitive bugs. No response-time or supported-version window is guaranteed at this stage.

Imports validate structure/counts but cannot certify publisher claims. Report failures with a reduced nonsensitive fixture, app version and error message. Protect local databases and exported draft JSON. Android stores mutable data privately and disables backup; export destinations are user-selected. Retain signing keys privately for compatible APK updates.
