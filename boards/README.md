# Boards

One directory per device, each with a `profile.json`. A device is installable only when
`release_status` is `released`, every `evidence` flag is true, an `identification` rule matches the
connected device and an `install_method` exists. All Kindle profiles are currently `research`:
nothing in them is verified. `qemu-x86_64` is a development target and can never be installed on a reader.

Fill a profile only with data measured on the device (`tools/hwdiag.sh` output). Never copy values from a
different model.
