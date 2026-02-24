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
    """Find all module.yaml files and return parsed manifests."""
    manifests = []
    for entry in sorted(os.listdir(modules_dir)):
        if filter_names and entry not in filter_names:
            continue
        yaml_path = os.path.join(modules_dir, entry, "module.yaml")
        if not os.path.isfile(yaml_path):
            continue
        with open(yaml_path) as f:
            manifest = yaml.safe_load(f)
        manifest.setdefault("name", entry)
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

        xcs_path = os.path.join(output_dir, "%s.xcs" % name)
        with open(xcs_path, "w") as f:
            f.write(generate_xcs(name, config))

        xcu_path = os.path.join(output_dir, "%s.xcu" % name)
        with open(xcu_path, "w") as f:
            f.write(generate_xcu(name, config))

        count += 1

    if count:
        print("  Generated %d XCS/XCU pairs in %s" % (count, output_dir))


def generate_manifest_xml(modules, output_path):
    """Generate META-INF/manifest.xml with XCS/XCU entries for selected modules."""
    # Static entries (always present)
    entries = [
        ('application/vnd.sun.star.uno-typelibrary;type=RDB', 'XPromptFunction.rdb'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/main.py'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/prompt_function.py'),
        ('application/vnd.sun.star.uno-component;type=Python', 'plugin/modules/chatbot/panel_factory.py'),
        ('application/vnd.sun.star.configuration-data', 'Addons.xcu'),
        ('application/vnd.sun.star.configuration-data', 'Accelerators.xcu'),
        ('application/vnd.sun.star.configuration-data', 'Jobs.xcu'),
        ('application/vnd.sun.star.configuration-data', 'registry/org/openoffice/Office/UI/Sidebar.xcu'),
        ('application/vnd.sun.star.configuration-data', 'registry/org/openoffice/Office/UI/Factories.xcu'),
    ]

    # Dynamic XCS/XCU entries for modules with config
    for m in modules:
        if not m.get("config"):
            continue
        name = m["name"]
        group = name.capitalize()
        entries.append(
            ('application/vnd.sun.star.configuration-schema',
             'registry/%s.xcs' % name))
        entries.append(
            ('application/vnd.sun.star.configuration-data',
             'registry/%s.xcu' % name))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE manifest:manifest PUBLIC "-//OpenOffice.org//DTD Manifest 1.0//EN" "Manifest.dtd">',
        '<manifest:manifest xmlns:manifest="http://openoffice.org/2001/manifest">',
    ]
    for media_type, full_path in entries:
        lines.append(
            '\t<manifest:file-entry manifest:media-type="%s"'
            ' manifest:full-path="%s"/>' % (media_type, full_path))
    lines.append('</manifest:manifest>')
    lines.append('')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
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

    print("Scanning modules in %s..." % modules_dir)
    manifests = find_modules(modules_dir, args.modules)
    if not manifests:
        print("  No modules found!")
        return 1

    sorted_modules = topo_sort(manifests)
    names = [m["name"] for m in sorted_modules]
    print("  Module order: %s" % " -> ".join(names))

    build_dir = os.path.join(PROJECT_ROOT, "build", "generated")

    # 1. _manifest.py
    manifest_path = os.path.join(PROJECT_ROOT, "plugin", "_manifest.py")
    generate_manifest_py(sorted_modules, manifest_path)

    # 2. XCS/XCU
    registry_dir = os.path.join(build_dir, "registry")
    generate_xcs_xcu(sorted_modules, registry_dir)

    # 3. META-INF/manifest.xml
    manifest_xml_path = os.path.join(PROJECT_ROOT, "extension", "META-INF", "manifest.xml")
    generate_manifest_xml(sorted_modules, manifest_xml_path)

    # 4. Patch version
    patch_description_xml(os.path.join(PROJECT_ROOT, "extension"))

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
