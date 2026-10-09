"""NetPilot-style Packet Tracer .pts extension creator.

Builds an encrypted PT "script module" (.pts) from a manifest + source files,
using the proven CAST256-EAX encrypt pipeline (pts_encrypt.encrypt_pts).

A .pts is: a PACKET_TRACER_SCRIPT_MODULE XML (manifest PT_APP_META + privileges
+ <SCRIPTS> of JS + <INTERFACES> of HTML/JS, each base64'd inside CDATA), then
qCompress/outer_xor x2 -> CAST256-EAX -> inner_xor. This module produces that
XML and encrypts it to a loadable .pts.

Usage:
    from pts_builder import build_pts
    build_pts("MyExt.pts", name="MyExt", module_id="com.me.myext",
              author="Me", scripts={"main.js": "queryTopology();"},
              interfaces={"index.html": "<html>..</html>"})
"""
from __future__ import annotations
import base64
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pts_encrypt import encrypt_pts  # noqa: E402

# Every privilege PT exposes to a script module (mirrors Builder.pts).
ALL_PRIVILEGES = [
    "GET_NETWORK_INFO", "CHANGE_NETWORK_INFO", "SIMULATION_MODE", "MISC_GUI",
    "FILE", "CHANGE_PREFERENCES", "CHANGE_GUI", "ACTIVITY_WIZARD", "MULTIUSER",
    "IPC", "APPLICATION",
]


def _cdata_b64(source) -> str:
    """Base64-encode a script/interface source and wrap it in a CDATA section,
    exactly as PT stores <CONTENT> bodies."""
    if isinstance(source, str):
        source = source.encode("utf-8")
    return "<![CDATA[" + base64.b64encode(source).decode("ascii") + "]]>"


def build_pts_xml(
    name: str,
    module_id: str,
    *,
    author: str = "",
    contact: str = "",
    description: str = "",
    version: str = "1.0",
    privileges=None,
    loading: str = "ON_STARTUP",      # ON_STARTUP | ON_DEMAND | NEVER
    saving: str = "NEVER",
    instances: int = 1,
    mandatory: bool = False,
    async_prompted: bool = True,
    detached: bool = False,
    scripts: dict | None = None,       # {"main.js": "<source>", ...}
    interfaces: dict | None = None,    # {"index.html": "<source>", ...}
    data_stores: dict | None = None,   # {"state.json": "<source>", ...}
    password: str = "",
    open_if_denied: bool = False,
) -> str:
    """Produce the PACKET_TRACER_SCRIPT_MODULE XML for a .pts (string)."""
    privileges = ALL_PRIVILEGES if privileges is None else list(privileges)
    scripts = scripts or {}
    interfaces = interfaces or {}
    data_stores = data_stores or {}

    priv_xml = "\n".join(f"    <PRIVILEGE>{escape(p)}</PRIVILEGE>" for p in privileges)
    scripts_xml = "\n".join(
        f"   <SCRIPT><ID>{escape(sid)}</ID><CONTENT>{_cdata_b64(src)}</CONTENT></SCRIPT>"
        for sid, src in scripts.items()
    )
    ds_xml = "\n".join(
        f"    <DATA_STORE><ID>{escape(did)}</ID><CONTENT>{_cdata_b64(src)}</CONTENT></DATA_STORE>"
        for did, src in data_stores.items()
    )
    iface_xml = "\n".join(
        f"   <INTERFACE><ID>{escape(iid)}</ID><CONTENT>{_cdata_b64(src)}</CONTENT></INTERFACE>"
        for iid, src in interfaces.items()
    )

    return (
        "<PACKET_TRACER_SCRIPT_MODULE>\n"
        " <SCRIPT_MODULE>\n"
        "  <PT_APP_META>\n"
        "   <PT_VERSION/>\n"
        "   <IPC_VERSION/>\n"
        f"   <NAME>{escape(name)}</NAME>\n"
        f"   <VERSION>{escape(version)}</VERSION>\n"
        f"   <ID>{escape(module_id)}</ID>\n"
        f"   <DESCRIPTION>{escape(description)}</DESCRIPTION>\n"
        f"   <AUTHOR>{escape(author)}</AUTHOR>\n"
        f"   <CONTACT>{escape(contact)}</CONTACT>\n"
        "   <EXECUTABLE_PATH/>\n"
        f"   <DETACHED>{str(detached).lower()}</DETACHED>\n"
        "   <KEY/>\n"
        "   <SECURITY_SETTINGS>\n"
        f"{priv_xml}\n"
        "   </SECURITY_SETTINGS>\n"
        f"   <LOADING>{escape(loading)}</LOADING>\n"
        f"   <SAVING>{escape(saving)}</SAVING>\n"
        f"   <INSTANCES>{int(instances)}</INSTANCES>\n"
        f"   <MANDATORY>{str(mandatory).lower()}</MANDATORY>\n"
        f"   <ASYNC_PROMPTED>{str(async_prompted).lower()}</ASYNC_PROMPTED>\n"
        "  </PT_APP_META>\n"
        f"  <PASSWORD>{escape(password)}</PASSWORD>\n"
        f"  <OPEN_IF_DENIED>{str(open_if_denied).lower()}</OPEN_IF_DENIED>\n"
        "  <SCRIPTS>\n"
        f"{scripts_xml}\n"
        "  <SCRIPT_DATA_STORES>\n"
        f"{ds_xml}\n"
        "  </SCRIPT_DATA_STORES>\n"
        "  </SCRIPTS>\n"
        "  <INTERFACES>\n"
        f"{iface_xml}\n"
        "  </INTERFACES>\n"
        "  <NEW_DEVICE_CUSTOM_INTERFACES/>\n"
        " </SCRIPT_MODULE>\n"
        "</PACKET_TRACER_SCRIPT_MODULE>"
    )


def build_pts(out_path: str, **kwargs) -> dict:
    """Build a .pts file at out_path. Returns {path, xml_len, pts_len}."""
    xml = build_pts_xml(**kwargs)
    data = encrypt_pts(xml.encode("utf-8"))
    with open(out_path, "wb") as f:
        f.write(data)
    return {"path": out_path, "xml_len": len(xml), "pts_len": len(data)}


def build_pts_from_dir(out_path: str, src_dir: str, **manifest) -> dict:
    """Build a .pts from a source directory. Files are classified by extension:
    .js -> SCRIPTS, .html/.htm/.css/.png/.svg/.woff* -> INTERFACES (UI assets),
    .json -> SCRIPT_DATA_STORES. `name`/`module_id` (+ optional author etc.)
    come from **manifest, or a manifest.json in the dir if present."""
    import json
    import os

    src_dir = os.path.abspath(src_dir)
    mf_path = os.path.join(src_dir, "manifest.json")
    if os.path.isfile(mf_path):
        with open(mf_path, encoding="utf-8") as f:
            mf = json.load(f)
        mf.update({k: v for k, v in manifest.items() if v is not None})
        manifest = mf

    scripts, interfaces, data_stores = {}, {}, {}
    for fn in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, fn)
        if not os.path.isfile(path) or fn == "manifest.json":
            continue
        ext = fn.rsplit(".", 1)[-1].lower()
        is_text = ext in ("js", "html", "htm", "css", "json", "svg", "txt", "xml")
        src = open(path, "r", encoding="utf-8").read() if is_text else open(path, "rb").read()
        if ext == "js":
            scripts[fn] = src
        elif ext == "json":
            data_stores[fn] = src
        else:
            interfaces[fn] = src
    return build_pts(out_path, scripts=scripts, interfaces=interfaces,
                     data_stores=data_stores, **manifest)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Build an encrypted Packet Tracer .pts extension.")
    ap.add_argument("out", help="output .pts path")
    ap.add_argument("--name", required=True)
    ap.add_argument("--id", dest="module_id", required=True, help="module id, e.g. com.me.ext")
    ap.add_argument("--author", default="")
    ap.add_argument("--contact", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--loading", default="ON_STARTUP", choices=["ON_STARTUP", "ON_DEMAND", "NEVER"])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--src-dir", help="directory of source files (.js/.html/.css/.json)")
    src.add_argument("--main-js", help="path to a single main.js to embed")
    args = ap.parse_args()

    meta = dict(name=args.name, module_id=args.module_id, author=args.author,
                contact=args.contact, description=args.description, version=args.version,
                loading=args.loading)
    if args.src_dir:
        res = build_pts_from_dir(args.out, args.src_dir, **meta)
    else:
        res = build_pts(args.out, scripts={"main.js": open(args.main_js, encoding="utf-8").read()}, **meta)
    print(json.dumps(res, indent=2))
