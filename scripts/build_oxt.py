#!/usr/bin/env python3
"""Build an .oxt LibreOffice extension from the plugin/ directory.

Usage:
    python3 scripts/build_oxt.py
    python3 scripts/build_oxt.py --modules core chatbot mcp openai_compat ollama
    python3 scripts/build_oxt.py --output build/localwriter.oxt
"""

import argparse
import os
import sys
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files/dirs always included from extension/
ALWAYS_INCLUDE_EXTENSION = [
    "extension/description.xml",
    "extension/META-INF/",
    "extension/Addons.xcu",
    "extension/Accelerators.xcu",
    "extension/Jobs.xcu",
    "extension/XPromptFunction.rdb",
    "extension/registration/",
    "extension/registry/",
    "extension/LocalWriterDialogs/",
    "extension/assets/",
]

# Files/dirs always included from plugin/
ALWAYS_INCLUDE_PLUGIN = [
    "plugin/__init__.py",
    "plugin/main.py",
    "plugin/version.py",
    "plugin/prompt_function.py",
    "plugin/_manifest.py",
    "plugin/framework/",
    "plugin/lib/",
]

# Module name -> paths under plugin/modules/
# When a module is selected, its entire directory is included
DEFAULT_MODULES = [
    "core", "writer", "calc", "draw",
    "openai_compat", "ollama", "horde",
    "chatbot", "mcp",
]

EXCLUDE_PATTERNS = (
    ".git",
    ".DS_Store",
    "__pycache__",
    ".pyc",
    ".pyo",
    "module.yaml",
    "tests/",
    "test_",
)

# Also include generated XCS/XCU
GENERATED_INCLUDES = [
    "build/generated/registry/",
]


def should_exclude(path):
    for pat in EXCLUDE_PATTERNS:
        if pat in path:
            return True
    return False


def collect_files(base_dir, include_paths):
    """Collect all files from a list of paths relative to base_dir."""
    files = []
    for inc in include_paths:
        full = os.path.join(base_dir, inc)
        if os.path.isfile(full):
            if not should_exclude(inc):
                files.append(inc)
        elif os.path.isdir(full):
            for root, dirs, filenames in os.walk(full):
                dirs[:] = [d for d in dirs if not should_exclude(d)]
                for fn in filenames:
                    filepath = os.path.join(root, fn)
                    relpath = os.path.relpath(filepath, base_dir)
                    if not should_exclude(relpath):
                        files.append(relpath)
        else:
            print("  WARNING: %s not found, skipping" % inc, file=sys.stderr)
    return sorted(set(files))


def build_oxt(base_dir, modules, output):
    """Build the .oxt file."""
    include = list(ALWAYS_INCLUDE_EXTENSION)
    include.extend(ALWAYS_INCLUDE_PLUGIN)

    # Add selected modules
    for mod in modules:
        mod_dir = "plugin/modules/%s/" % mod
        mod_path = os.path.join(base_dir, mod_dir)
        if os.path.isdir(mod_path):
            include.append(mod_dir)
        else:
            print("  WARNING: module '%s' not found at %s" % (mod, mod_dir),
                  file=sys.stderr)

    # Add generated files (XCS/XCU)
    include.extend(GENERATED_INCLUDES)

    files = collect_files(base_dir, include)

    # Build output path
    output_path = os.path.join(base_dir, output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            src = os.path.join(base_dir, f)
            # Remap paths for the .oxt archive
            if f.startswith("extension/"):
                arcname = f[len("extension/"):]
            elif f.startswith("build/generated/registry/"):
                arcname = f.replace("build/generated/", "")
            else:
                arcname = f
            zf.write(src, arcname)

    print("Created %s with %d files (modules: %s)" % (
        output, len(files), ", ".join(modules)))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build LocalWriter .oxt extension")
    parser.add_argument(
        "--modules", nargs="+", default=DEFAULT_MODULES,
        help="Modules to include (default: all)")
    parser.add_argument(
        "--output", default="build/localwriter.oxt",
        help="Output file (default: build/localwriter.oxt)")
    args = parser.parse_args()

    return build_oxt(PROJECT_ROOT, args.modules, args.output)


if __name__ == "__main__":
    sys.exit(main())
