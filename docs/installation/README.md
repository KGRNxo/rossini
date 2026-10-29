# Installation

**There is no installable device image and no device is released.** `tools/install.command` exists to prove the process
and the gate; today it always ends with a refusal and a diagnose report.

Steps the assistant performs (implemented in `rossini/installer`): read the mounted device (read-only) -> verify the image signature and
board -> evaluate the gate -> back up `documents/` with hash verification -> install. The gate demands: exactly one board profile whose
identification rules match; `release_status: released`; all four `evidence` flags; an `install_method`; verified image for that board; finished backup.
There is no `--force`. The last step (flashing) is not implemented and raises `NotImplementedError` by design.

To refuse and collect data on your own device: `./tools/install.command /Volumes/Kindle` and attach the `rossini-diagnose-*.json`
(serial numbers are cut to 4 characters) when opening a hardware issue.

Prerequisites before this may change: docs/hardware/README.md items 1-3.
