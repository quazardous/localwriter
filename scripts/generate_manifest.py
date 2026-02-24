#!/usr/bin/env python3
"""Generate _manifest.py and XCS/XCU from module.yaml files.

Reads each module.yaml under plugin/modules/, validates it, and produces:
  - build/generated/_manifest.py     — Python dict for runtime
  - build/generated/registry/*.xcs   — LO config schemas
  - build/generated/registry/*.xcu   — LO config defaults
  - Patches description.xml with version from plugin/version.py

Usage:
    python3 scripts/generate_manifest.py
    python3 scripts/generate_manifest.py --modules core mcp openai_compat
"""

import argparse
import json
import os
import re
import sys

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml",
          file=sys.stderr)
    sys.exit(1)


def find_modules(modules_dir, filter_names=None):
    """Find all module.yaml files recursively and return parsed manifests.

    Module name comes from the ``name`` field in module.yaml.
    Directory convention: dots map to underscores (tunnel.bore -> tunnel_bore/).
    Falls back to directory-derived name if ``name`` is absent.
    """
    manifests = []
    for dirpath, dirnames, filenames in os.walk(modules_dir):
        if "module.yaml" not in filenames:
            continue
        # Build dotted module name from relative path
        rel = os.path.relpath(dirpath, modules_dir)
        module_name = rel.replace(os.sep, ".")

        if filter_names:
            top_level = module_name.split(".")[0]
            if module_name not in filter_names and top_level not in filter_names:
                continue

        yaml_path = os.path.join(dirpath, "module.yaml")
        with open(yaml_path) as f:
            manifest = yaml.safe_load(f)
        manifest.setdefault("name", module_name)
        manifests.append(manifest)

    return manifests


def topo_sort(modules):
    """Sort modules by dependency order (core first)."""
    by_name = {m["name"]: m for m in modules}
    provides = {}
    for m in modules:
        for svc in m.get("provides_services", []):
            provides[svc] = m["name"]

    visited = set()
    order = []

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        m = by_name.get(name)
        if m is None:
            return
        for req in m.get("requires", []):
            provider = provides.get(req, req)
            if provider in by_name:
                visit(provider)
        order.append(m)

    if "core" in by_name:
        visit("core")
    for name in by_name:
        visit(name)

    return order


def _json_to_python(text):
    """Convert JSON literals to Python literals (true->True, false->False, null->None)."""
    # Only replace JSON keywords when they appear as values, not inside strings
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if in_string:
            result.append(ch)
            i += 1
            continue
        # Outside string: replace JSON keywords
        for jval, pyval in (("true", "True"), ("false", "False"), ("null", "None")):
            if text[i:i+len(jval)] == jval:
                # Check it's a whole word (not part of a larger identifier)
                before_ok = (i == 0 or not text[i-1].isalnum())
                after_ok = (i + len(jval) >= len(text) or not text[i+len(jval)].isalnum())
                if before_ok and after_ok:
                    result.append(pyval)
                    i += len(jval)
                    break
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def generate_manifest_py(modules, output_path):
    """Generate _manifest.py with module descriptors as Python dicts."""
    from plugin.version import EXTENSION_VERSION

    lines = [
        '"""Auto-generated module manifest. DO NOT EDIT."""',
        "",
        "VERSION = %r" % EXTENSION_VERSION,
        "",
        "MODULES = [",
    ]
    for m in modules:
        # Clean repr — only keep runtime-relevant keys
        entry = {
            "name": m["name"],
            "description": m.get("description", ""),
            "requires": m.get("requires", []),
            "provides_services": m.get("provides_services", []),
            "config": m.get("config", {}),
        }
        # json.dumps then convert true/false/null to Python True/False/None
        json_text = json.dumps(entry, indent=8)
        lines.append("    %s," % _json_to_python(json_text))
    lines.append("]")
    lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print("  Generated %s (%d modules)" % (output_path, len(modules)))


def generate_xcs_xcu(modules, output_dir):
    """Generate XCS/XCU files for modules with config."""
    from plugin.framework.config_schema import generate_xcs, generate_xcu

    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for m in modules:
        config = m.get("config", {})
        if not config:
            continue

        name = m["name"]
        safe = name.replace(".", "_")

        xcs_path = os.path.join(output_dir, "%s.xcs" % safe)
        with open(xcs_path, "w") as f:
            f.write(generate_xcs(name, config))

        xcu_path = os.path.join(output_dir, "%s.xcu" % safe)
        with open(xcu_path, "w") as f:
            f.write(generate_xcu(name, config))

        count += 1

    if count:
        print("  Generated %d XCS/XCU pairs in %s" % (count, output_dir))


# ── XDL Generation (using xml.etree.ElementTree) ─────────────────────

import xml.etree.ElementTree as ET

# Layout constants for XDL pages (dialog units)
_PAGE_WIDTH = 260
_PAGE_HEIGHT = 260
_MARGIN = 6
_LABEL_WIDTH = 100
_FIELD_X = 110
_FIELD_WIDTH = 144
_ROW_HEIGHT = 14
_ROW_GAP = 4
_HELPER_HEIGHT = 10
_HELPER_GAP = 1
_BROWSE_BTN_WIDTH = 20
_BROWSE_BTN_GAP = 2

_DLG_NS = "http://openoffice.org/2000/dialog"
_SCRIPT_NS = "http://openoffice.org/2000/script"
_OOR_NS = "http://openoffice.org/2001/registry"
_XS_NS = "http://www.w3.org/2001/XMLSchema"

ET.register_namespace("dlg", _DLG_NS)
ET.register_namespace("script", _SCRIPT_NS)
ET.register_namespace("oor", _OOR_NS)
ET.register_namespace("xs", _XS_NS)


def _dlg(local):
    """Qualified name in dlg: namespace."""
    return "{%s}%s" % (_DLG_NS, local)


def _oor(local):
    """Qualified name in oor: namespace."""
    return "{%s}%s" % (_OOR_NS, local)


def _common_attrs(field_name, y, width=None, height=None):
    """Common XDL element attributes."""
    return {
        _dlg("id"): field_name,
        _dlg("tab-index"): "0",
        _dlg("left"): str(_FIELD_X),
        _dlg("top"): str(y),
        _dlg("width"): str(width or _FIELD_WIDTH),
        _dlg("height"): str(height or _ROW_HEIGHT),
    }


def _add_checkbox(board, field_name, schema, y):
    attrs = _common_attrs(field_name, y)
    attrs[_dlg("checked")] = "false"
    ET.SubElement(board, _dlg("checkbox"), attrs)


def _add_textfield(board, field_name, schema, y, echo_char=None, multiline=False):
    h = _ROW_HEIGHT * 3 if multiline else _ROW_HEIGHT
    attrs = _common_attrs(field_name, y, height=h)
    if echo_char:
        attrs[_dlg("echochar")] = str(echo_char)
    if multiline:
        attrs[_dlg("multiline")] = "true"
        attrs[_dlg("vscroll")] = "true"
    ET.SubElement(board, _dlg("textfield"), attrs)


def _add_numericfield(board, field_name, schema, y):
    attrs = _common_attrs(field_name, y)
    attrs[_dlg("spin")] = "true"
    if "min" in schema:
        attrs[_dlg("value-min")] = str(schema["min"])
    if "max" in schema:
        attrs[_dlg("value-max")] = str(schema["max"])
    if "step" in schema:
        attrs[_dlg("value-step")] = str(schema["step"])
    attrs[_dlg("decimal-accuracy")] = "1" if schema.get("type") == "float" else "0"
    ET.SubElement(board, _dlg("numericfield"), attrs)


def _add_menulist(board, field_name, schema, y):
    attrs = _common_attrs(field_name, y)
    attrs[_dlg("spin")] = "true"
    attrs[_dlg("dropdown")] = "true"
    ET.SubElement(board, _dlg("menulist"), attrs)


def _add_label(board, field_name, label_text, y):
    attrs = {
        _dlg("id"): "lbl_%s" % field_name,
        _dlg("tab-index"): "0",
        _dlg("left"): str(_MARGIN),
        _dlg("top"): str(y + 2),
        _dlg("width"): str(_LABEL_WIDTH),
        _dlg("height"): str(_ROW_HEIGHT),
        _dlg("value"): label_text,
    }
    ET.SubElement(board, _dlg("text"), attrs)


def _add_filefield(board, field_name, schema, y):
    """Add a textfield + browse button for file/folder widgets."""
    field_w = _FIELD_WIDTH - _BROWSE_BTN_WIDTH - _BROWSE_BTN_GAP
    attrs = _common_attrs(field_name, y, width=field_w)
    ET.SubElement(board, _dlg("textfield"), attrs)
    # Browse button "..."
    btn_x = _FIELD_X + field_w + _BROWSE_BTN_GAP
    btn_attrs = {
        _dlg("id"): "btn_%s" % field_name,
        _dlg("tab-index"): "0",
        _dlg("left"): str(btn_x),
        _dlg("top"): str(y),
        _dlg("width"): str(_BROWSE_BTN_WIDTH),
        _dlg("height"): str(_ROW_HEIGHT),
        _dlg("value"): "...",
    }
    ET.SubElement(board, _dlg("button"), btn_attrs)


def _add_helper(board, field_name, helper_text, y):
    """Add a small helper text below a field, spanning full page width."""
    helper_width = _PAGE_WIDTH - _MARGIN * 2
    attrs = {
        _dlg("id"): "hlp_%s" % field_name,
        _dlg("tab-index"): "0",
        _dlg("left"): str(_MARGIN),
        _dlg("top"): str(y),
        _dlg("width"): str(helper_width),
        _dlg("height"): str(_HELPER_HEIGHT),
        _dlg("value"): helper_text,
    }
    ET.SubElement(board, _dlg("text"), attrs)


def _xdl_to_string(root):
    """Serialize XDL element tree to string with XML declaration and DOCTYPE."""
    ET.indent(root, space="  ")
    xml_body = ET.tostring(root, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE dlg:window PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "dialog.dtd">\n'
        + xml_body + "\n"
    )


def generate_xdl(module_name, config_fields):
    """Generate an XDL dialog page for a module's config fields."""
    page_id = "LocalWriter_%s" % module_name.replace(".", "_")

    window = ET.Element(_dlg("window"), {
        _dlg("id"): page_id,
        _dlg("left"): "0",
        _dlg("top"): "0",
        _dlg("width"): str(_PAGE_WIDTH),
        _dlg("height"): str(_PAGE_HEIGHT),
        _dlg("closeable"): "true",
        _dlg("withtitlebar"): "false",
    })
    # Force namespace declarations on root
    window.set("xmlns:script", _SCRIPT_NS)

    board = ET.SubElement(window, _dlg("bulletinboard"))

    # Hidden control to identify the module
    ET.SubElement(board, _dlg("text"), {
        _dlg("id"): "__module__",
        _dlg("tab-index"): "0",
        _dlg("left"): "0", _dlg("top"): "0",
        _dlg("width"): "0", _dlg("height"): "0",
        _dlg("value"): module_name,
    })

    y = _MARGIN

    for field_name, schema in config_fields.items():
        widget = schema.get("widget", "text")
        label_text = schema.get("label", field_name)

        _add_label(board, field_name, label_text, y)

        if widget == "checkbox":
            _add_checkbox(board, field_name, schema, y)
        elif widget == "password":
            _add_textfield(board, field_name, schema, y, echo_char=42)
        elif widget == "textarea":
            _add_textfield(board, field_name, schema, y, multiline=True)
            y += _ROW_HEIGHT * 2
        elif widget in ("number", "slider"):
            _add_numericfield(board, field_name, schema, y)
        elif widget == "select":
            _add_menulist(board, field_name, schema, y)
        elif widget in ("file", "folder"):
            _add_filefield(board, field_name, schema, y)
        else:
            _add_textfield(board, field_name, schema, y)

        y += _ROW_HEIGHT

        helper_text = schema.get("helper")
        if helper_text:
            y += _HELPER_GAP
            _add_helper(board, field_name, helper_text, y)
            y += _HELPER_HEIGHT

        y += _ROW_GAP

    return _xdl_to_string(window)


def generate_xdl_files(modules, output_dir):
    """Generate XDL dialog files for modules with config."""
    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for m in modules:
        config = m.get("config", {})
        if not config:
            continue

        name = m["name"]
        safe = name.replace(".", "_")
        xdl_path = os.path.join(output_dir, "%s.xdl" % safe)
        with open(xdl_path, "w") as f:
            f.write(generate_xdl(name, config))
        count += 1

    if count:
        print("  Generated %d XDL dialog pages in %s" % (count, output_dir))


# ── OptionsDialog.xcu Generation ─────────────────────────────────────


def _pretty_name(module_name):
    """Convert module_name to a pretty display label."""
    # For dotted names like "tunnel.bore", use last part
    last = module_name.rsplit(".", 1)[-1]
    return last.replace("_", " ").title()


def generate_options_dialog_xcu(modules):
    """Generate OptionsDialog.xcu for the LO options tree.

    LO OptionsDialog schema: top-level ``Nodes`` set contains ``Node`` groups,
    each ``Node`` has a ``Leaves`` set. Nodes do NOT nest — sub-module groups
    become separate top-level Nodes (like "LibreOffice" / "LibreOffice Writer").

    Structure produced::

        Nodes
        ├── LocalWriter (Node)
        │   └── Leaves: [Main], Core, Http, Mcp, Chatbot ...
        ├── LocalWriter Tunnel (Node)    ← only if tunnel has sub-modules
        │   └── Leaves: Main, Ngrok, Bore, Cloudflare
        └── ...
    """
    handler_service = "org.extension.localwriter.OptionsHandler"

    root = ET.Element(_oor("component-data"), {
        _oor("name"): "OptionsDialog",
        _oor("package"): "org.openoffice.Office",
    })
    root.set("xmlns:xs", _XS_NS)

    nodes_el = ET.SubElement(root, "node", {_oor("name"): "Nodes"})

    # Classify modules
    top_level = []       # modules without dots (in order)
    children = {}        # parent_name -> [child_modules] (in order)
    has_children = set()

    for m in modules:
        name = m["name"]
        if "." in name:
            parent = name.rsplit(".", 1)[0]
            children.setdefault(parent, []).append(m)
            has_children.add(parent)
        else:
            top_level.append(m)

    # ── Main Node: "LocalWriter" ─────────────────────────────────────
    lw_node_name = "LocalWriter"
    lw_node = _add_node(nodes_el, lw_node_name, "LocalWriter")
    lw_leaves = ET.SubElement(lw_node, "node", {_oor("name"): "Leaves"})

    # GroupId matches parent Node oor:name → appears first group.
    # GroupIndex controls display order within the group.
    group_idx = 0

    # Framework-level "Main" leaf (always first if it has config)
    for m in top_level:
        if m["name"] == "main" and m.get("config"):
            _add_leaf(lw_leaves, "LocalWriter_main", "Main",
                      "main", "main", handler_service,
                      group_id=lw_node_name, group_index=group_idx)
            group_idx += 1
            break

    # Simple modules (no sub-modules) as leaves under LocalWriter
    for m in top_level:
        name = m["name"]
        if name == "main" or name in has_children:
            continue
        config = m.get("config", {})
        if not config:
            continue
        safe = name.replace(".", "_")
        _add_leaf(lw_leaves, "LocalWriter_%s" % safe, _pretty_name(name),
                  name, safe, handler_service,
                  group_id=lw_node_name, group_index=group_idx)
        group_idx += 1

    # ── Sub-module groups as leaves under LocalWriter ────────────────
    # LO doesn't reliably show multiple top-level Nodes from one extension.
    # Instead, add parent + children as leaves with a group separator label.
    for m in top_level:
        name = m["name"]
        if name not in has_children:
            continue

        config = m.get("config", {})

        # Parent's own config (labeled "Tunnel" not "Main" since it's flat)
        if config:
            safe = name.replace(".", "_")
            _add_leaf(lw_leaves, "LocalWriter_%s" % safe,
                      _pretty_name(name),
                      name, safe, handler_service,
                      group_id=lw_node_name, group_index=group_idx)
            group_idx += 1

        # Sub-module leaves (labeled "Tunnel: Ngrok" etc.)
        for child in children.get(name, []):
            child_name = child["name"]
            child_config = child.get("config", {})
            if not child_config:
                continue
            child_safe = child_name.replace(".", "_")
            # Label: "Tunnel: Ngrok"
            child_label = "%s: %s" % (_pretty_name(name),
                                      _pretty_name(child_name))
            _add_leaf(lw_leaves, "LocalWriter_%s" % child_safe,
                      child_label,
                      child_name, child_safe, handler_service,
                      group_id=lw_node_name, group_index=group_idx)
            group_idx += 1

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _add_node(parent, node_name, label):
    """Add a Node element to the OptionsDialog Nodes set."""
    node = ET.SubElement(parent, "node", {
        _oor("name"): node_name,
        _oor("op"): "fuse",
    })
    label_prop = ET.SubElement(node, "prop", {_oor("name"): "Label"})
    ET.SubElement(label_prop, "value").text = label
    all_mod_prop = ET.SubElement(node, "prop", {_oor("name"): "AllModules"})
    ET.SubElement(all_mod_prop, "value").text = "true"
    return node


def _add_leaf(parent, node_name, label, module_name, safe_name,
              handler_service, group_id=None, group_index=None):
    """Add a leaf node to the OptionsDialog XCU tree."""
    leaf = ET.SubElement(parent, "node", {
        _oor("name"): node_name,
        _oor("op"): "fuse",
    })

    id_prop = ET.SubElement(leaf, "prop", {_oor("name"): "Id"})
    ET.SubElement(id_prop, "value").text = "org.extension.localwriter"

    lbl_prop = ET.SubElement(leaf, "prop", {_oor("name"): "Label"})
    ET.SubElement(lbl_prop, "value").text = label

    page_prop = ET.SubElement(leaf, "prop", {_oor("name"): "OptionsPage"})
    ET.SubElement(page_prop, "value").text = "%%origin%%/dialogs/%s.xdl" % safe_name

    handler_prop = ET.SubElement(leaf, "prop", {_oor("name"): "EventHandlerService"})
    ET.SubElement(handler_prop, "value").text = handler_service

    if group_id is not None:
        gid_prop = ET.SubElement(leaf, "prop", {_oor("name"): "GroupId"})
        ET.SubElement(gid_prop, "value").text = group_id
    if group_index is not None:
        gix_prop = ET.SubElement(leaf, "prop", {_oor("name"): "GroupIndex"})
        ET.SubElement(gix_prop, "value").text = str(group_index)


def generate_manifest_xml(modules, output_path):
    """Generate META-INF/manifest.xml with XCS/XCU entries for selected modules."""
    MANIFEST_NS = "http://openoffice.org/2001/manifest"
    MF = "manifest:"

    # Static entries (always present)
    entries = [
        ('application/vnd.sun.star.uno-typelibrary;type=RDB', 'XPromptFunction.rdb'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/main.py'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/prompt_function.py'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/options_handler.py'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/modules/chatbot/panel_factory.py'),
        ('application/vnd.sun.star.configuration-data', 'Addons.xcu'),
        ('application/vnd.sun.star.configuration-data', 'Accelerators.xcu'),
        ('application/vnd.sun.star.configuration-data', 'Jobs.xcu'),
        ('application/vnd.sun.star.configuration-data', 'OptionsDialog.xcu'),
        ('application/vnd.sun.star.configuration-data', 'registry/org/openoffice/Office/UI/Sidebar.xcu'),
        ('application/vnd.sun.star.configuration-data', 'registry/org/openoffice/Office/UI/Factories.xcu'),
    ]

    # Dynamic XCS/XCU entries for modules with config
    for m in modules:
        if not m.get("config"):
            continue
        safe = m["name"].replace(".", "_")
        entries.append(
            ('application/vnd.sun.star.configuration-schema',
             'registry/%s.xcs' % safe))
        entries.append(
            ('application/vnd.sun.star.configuration-data',
             'registry/%s.xcu' % safe))

    # Build XML tree
    def _mf(tag):
        return "{%s}%s" % (MANIFEST_NS, tag)

    ET.register_namespace("manifest", MANIFEST_NS)
    root = ET.Element(_mf("manifest"))
    for media_type, full_path in entries:
        ET.SubElement(root, _mf("file-entry"), {
            _mf("media-type"): media_type,
            _mf("full-path"): full_path,
        })

    ET.indent(root, space="\t")
    body = ET.tostring(root, encoding="unicode")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!-- GENERATED FILE — do not edit manually. -->\n")
        f.write("<!-- Re-generated by: scripts/generate_manifest.py -->\n")
        f.write(body)
        f.write("\n")
    print("  Generated %s (%d entries)" % (output_path, len(entries)))


def patch_description_xml(extension_dir):
    """Patch description.xml with version from plugin/version.py."""
    from plugin.version import EXTENSION_VERSION

    desc_path = os.path.join(extension_dir, "description.xml")
    if not os.path.exists(desc_path):
        print("  WARNING: description.xml not found, skipping version patch")
        return

    with open(desc_path) as f:
        content = f.read()

    # Replace version value
    new_content = re.sub(
        r'<version value="[^"]*"/>',
        '<version value="%s"/>' % EXTENSION_VERSION,
        content,
    )

    if new_content != content:
        with open(desc_path, "w") as f:
            f.write(new_content)
        print("  Patched description.xml with version %s" % EXTENSION_VERSION)
    else:
        print("  description.xml already at version %s" % EXTENSION_VERSION)


def main():
    parser = argparse.ArgumentParser(
        description="Generate _manifest.py and XCS/XCU from module.yaml files")
    parser.add_argument(
        "--modules", nargs="*", default=None,
        help="Only process these modules (default: all)")
    args = parser.parse_args()

    modules_dir = os.path.join(PROJECT_ROOT, "plugin", "modules")
    if not os.path.isdir(modules_dir):
        print("ERROR: plugin/modules/ not found at %s" % modules_dir,
              file=sys.stderr)
        return 1

    # Load framework-level plugin.yaml (if present)
    plugin_yaml_path = os.path.join(PROJECT_ROOT, "plugin", "plugin.yaml")
    framework_manifest = None
    if os.path.isfile(plugin_yaml_path):
        with open(plugin_yaml_path) as f:
            framework_manifest = yaml.safe_load(f)
        framework_manifest.setdefault("name", "main")
        print("  Loaded framework config: plugin/plugin.yaml")

    print("Scanning modules in %s..." % modules_dir)
    manifests = find_modules(modules_dir, args.modules)
    if not manifests:
        print("  No modules found!")
        return 1

    sorted_modules = topo_sort(manifests)

    # Prepend framework manifest (always first, before all modules)
    if framework_manifest:
        sorted_modules.insert(0, framework_manifest)
    names = [m["name"] for m in sorted_modules]
    print("  Module order: %s" % " -> ".join(names))

    build_dir = os.path.join(PROJECT_ROOT, "build", "generated")

    # 1. _manifest.py
    manifest_path = os.path.join(PROJECT_ROOT, "plugin", "_manifest.py")
    generate_manifest_py(sorted_modules, manifest_path)

    # 2. XCS/XCU
    registry_dir = os.path.join(build_dir, "registry")
    generate_xcs_xcu(sorted_modules, registry_dir)

    # 3. XDL dialog pages
    dialogs_dir = os.path.join(build_dir, "dialogs")
    generate_xdl_files(sorted_modules, dialogs_dir)

    # 4. OptionsDialog.xcu
    options_xcu_path = os.path.join(build_dir, "OptionsDialog.xcu")
    with open(options_xcu_path, "w") as f:
        f.write(generate_options_dialog_xcu(sorted_modules))
    print("  Generated %s" % options_xcu_path)

    # 5. META-INF/manifest.xml
    manifest_xml_path = os.path.join(PROJECT_ROOT, "extension", "META-INF", "manifest.xml")
    generate_manifest_xml(sorted_modules, manifest_xml_path)

    # 6. Patch version
    patch_description_xml(os.path.join(PROJECT_ROOT, "extension"))

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
