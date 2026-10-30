"""Signed update packages. A package is a plain tar: manifest.json, manifest.sig (Ed25519 over the
exact manifest bytes) and the payload files named in the manifest with size and sha256.
Verification order: signature -> product/board/rollback policy -> streamed payload hashing into a
staging directory. Nothing is written to a slot before every check passed."""
import hashlib
import io
import json
import os
import tarfile
import time

from . import ed25519

PRODUCT = "rossini-os"
MAX_MANIFEST = 1 << 20
MAX_PAYLOAD = 2 << 30


class PackageError(Exception):
    pass


def generate_keypair():
    """Host-side only (needs the cryptography package)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    k = Ed25519PrivateKey.generate()
    return (k.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()),
            k.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def build(out_path, version, rollback_index, boards, payloads, private_key, created=None):
    """payloads: {name: path}. Returns the manifest dict."""
    entries = []
    for name, path in payloads.items():
        h, size = hashlib.sha256(), 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
                size += len(chunk)
        entries.append({"name": name, "sha256": h.hexdigest(), "size": size})
    manifest = {"format": 1, "product": PRODUCT, "version": version, "rollback_index": rollback_index,
                "boards": list(boards), "created": int(time.time() if created is None else created), "payloads": entries}
    raw = json.dumps(manifest, sort_keys=True, indent=1).encode()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # host-side only
    sig = Ed25519PrivateKey.from_private_bytes(private_key).sign(raw)
    with tarfile.open(out_path, "w", format=tarfile.USTAR_FORMAT) as t:
        for name, data in (("manifest.json", raw), ("manifest.sig", sig)):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime = len(data), created or 0
            t.addfile(ti, io.BytesIO(data))
        for name, path in payloads.items():
            ti = t.gettarinfo(path, arcname=name)
            ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname, ti.mode = created or ti.mtime, 0, 0, "", "", 0o644
            with open(path, "rb") as f:
                t.addfile(ti, f)
    return manifest


def verify(pkg_path, trusted_keys, board, current_rollback_index, staging_dir):
    """Verify and stage. Returns (manifest, {name: staged_path}). Raises PackageError with a readable reason."""
    try:
        return _verify(pkg_path, trusted_keys, board, current_rollback_index, staging_dir)
    except (tarfile.TarError, EOFError) as e:
        raise PackageError(f"Paket beschädigt oder abgeschnitten: {e}")


def _verify(pkg_path, trusted_keys, board, current_rollback_index, staging_dir):
    try:
        t = tarfile.open(pkg_path, "r:")
    except (tarfile.TarError, OSError) as e:
        raise PackageError(f"Paket nicht lesbar: {e}")
    with t:
        members = {}
        for m in t.getmembers():
            if not m.isreg() or m.name.startswith("/") or ".." in m.name.split("/") or "/" in m.name:
                raise PackageError(f"unzulässiger Paketeintrag: {m.name!r}")
            if m.name in members:
                raise PackageError(f"doppelter Paketeintrag: {m.name}")
            members[m.name] = m
        if "manifest.json" not in members or "manifest.sig" not in members:
            raise PackageError("Manifest oder Signatur fehlt")
        if members["manifest.json"].size > MAX_MANIFEST or members["manifest.sig"].size != 64:
            raise PackageError("Manifest oder Signatur hat ungültige Größe")
        raw = t.extractfile(members["manifest.json"]).read()
        sig = t.extractfile(members["manifest.sig"]).read()
        if not any(ed25519.verify(k, raw, sig) for k in trusted_keys):
            raise PackageError("Signatur ungültig: das Paket stammt nicht von einem vertrauten Schlüssel")
        try:
            man = json.loads(raw)
            assert man["format"] == 1 and isinstance(man["payloads"], list)
        except (ValueError, KeyError, AssertionError):
            raise PackageError("Manifest fehlerhaft")
        if man.get("product") != PRODUCT:
            raise PackageError("Paket gehört nicht zu Rossini OS")
        if board not in man.get("boards", []):
            raise PackageError(f"Paket ist nicht für dieses Gerät ({board}) freigegeben")
        if int(man["rollback_index"]) < current_rollback_index:
            raise PackageError("Downgrade abgelehnt: Paket ist älter als die installierte Version")
        declared = {p["name"]: p for p in man["payloads"]}
        if set(declared) != set(members) - {"manifest.json", "manifest.sig"}:
            raise PackageError("Paketinhalt stimmt nicht mit dem Manifest überein")
        os.makedirs(staging_dir, exist_ok=True)
        staged = {}
        for name, p in declared.items():
            if not isinstance(p["size"], int) or p["size"] > MAX_PAYLOAD or members[name].size != p["size"]:
                raise PackageError(f"Größe von {name} stimmt nicht")
            h, dest = hashlib.sha256(), os.path.join(staging_dir, name)
            with t.extractfile(members[name]) as src, open(dest, "wb") as dst:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    h.update(chunk)
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            if h.hexdigest() != p["sha256"]:
                raise PackageError(f"Prüfsumme von {name} stimmt nicht")
            staged[name] = dest
    return man, staged
