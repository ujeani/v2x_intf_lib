import os
import re
import tempfile

import asn1tools


DEFAULT_J2735_ASN_DIR = "J2735SET_202409"


def resolve_asn_dir(asn_dir_name: str = DEFAULT_J2735_ASN_DIR) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, asn_dir_name),
        os.path.join(os.getcwd(), asn_dir_name),
    ]

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    raise FileNotFoundError(
        f"ASN.1 directory '{asn_dir_name}' not found. Checked: {candidates}"
    )


def _read_asn_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="strict") as src_file:
        try:
            return src_file.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="cp1252", errors="replace") as cp_file:
                return cp_file.read()


def _create_compat_asn_files(asn_files: list[str]) -> tuple[str, list[str]]:
    tmp_dir = tempfile.mkdtemp(prefix="j2735_asn_compat_")
    compat_files = []

    for src_path in asn_files:
        contents = _read_asn_file(src_path)

        # asn1tools does not resolve RELATIVE-OID in this dataset; map it for compatibility.
        contents = re.sub(r"\bRELATIVE-OID\b", "OBJECT IDENTIFIER", contents)

        dst_path = os.path.join(tmp_dir, os.path.basename(src_path))
        with open(dst_path, "w", encoding="utf-8", newline="") as dst_file:
            dst_file.write(contents)

        compat_files.append(dst_path)

    return tmp_dir, compat_files


def list_asn_files(asn_dir_name: str = DEFAULT_J2735_ASN_DIR) -> tuple[str, list[str]]:
    asn_dir = resolve_asn_dir(asn_dir_name)
    asn_files = [
        os.path.join(asn_dir, filename)
        for filename in os.listdir(asn_dir)
        if filename.lower().endswith(".asn")
    ]
    asn_files.sort()
    return asn_dir, asn_files


def compile_j2735_spec(asn_dir_name: str = DEFAULT_J2735_ASN_DIR):
    asn_dir, asn_files = list_asn_files(asn_dir_name)
    print(f"Found {len(asn_files)} ASN.1 files in '{asn_dir}':")

    try:
        return asn1tools.compile_files(asn_files, codec="uper")
    except asn1tools.errors.CompileError as exc:
        if "RELATIVE-OID" not in str(exc):
            raise

        print("asn1tools compatibility mode enabled: replacing RELATIVE-OID with OBJECT IDENTIFIER.")
        _, compat_asn_files = _create_compat_asn_files(asn_files)
        return asn1tools.compile_files(compat_asn_files, codec="uper")
