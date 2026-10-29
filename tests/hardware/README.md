# Hardware test protocol

These tests cannot be automated from a PC and have never been executed. Record results per device in
`tests/hardware/results/<board>-<date>.md` (device serial prefix only), then set the matching `evidence` flag in the board profile.

For each device: cold start · restart · display output · E-Ink full/partial refresh and ghosting · touchscreen · keys ·
frontlight · WLAN · USB · battery gauge · charging · standby · resume · reading every supported format ·
memory pressure with a 500-book library · power cut during update (slot untouched, old system boots) ·
recovery after a bad update (rollback after 3 tries) · recovery from an unbootable kernel using the independent path.

Measure: cold start time, standby current, resume time, battery life with a fixed reading script. No improvement may be claimed without these numbers.
