"""Auto-generated settings dialog from module manifests.

Reads _manifest.py and builds a tabbed dialog with one tab per module,
using the widget types declared in each module.yaml config section.

UNO widget mapping:
  checkbox  -> UnoControlCheckBox
  text      -> UnoControlEdit
  password  -> UnoControlEdit (EchoChar=42)
  textarea  -> UnoControlEdit (MultiLine)
  number    -> UnoControlNumericField
  slider    -> UnoControlNumericField + label (slider not great in UNO)
  select    -> UnoControlListBox
  file      -> UnoControlEdit + Browse button
  folder    -> UnoControlEdit + Browse button
"""

import logging

log = logging.getLogger("localwriter.settings")

# Layout constants (in dialog units ~= 1/4 pixel on most DPIs)
_DLG_WIDTH = 380
_DLG_HEIGHT = 320
_TAB_HEIGHT = 24
_MARGIN = 10
_LABEL_WIDTH = 120
_FIELD_X = 140
_FIELD_WIDTH = 220
_ROW_HEIGHT = 18
_ROW_GAP = 4
_BROWSE_BTN_WIDTH = 30


def show_settings(ctx, config_service, manifest_modules):
    """Show the settings dialog.

    Args:
        ctx: UNO component context.
        config_service: ConfigService instance.
        manifest_modules: list of module dicts from _manifest.py.

    Returns:
        True if OK was pressed, False if cancelled.
    """
    import uno

    smgr = ctx.ServiceManager

    # ── Build dialog model ────────────────────────────────────────────

    dlg_model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialogModel", ctx)
    dlg_model.Title = "LocalWriter Settings"
    dlg_model.Width = _DLG_WIDTH
    dlg_model.Height = _DLG_HEIGHT

    # Filter modules that have config fields
    tabs = [(m["name"], m.get("description", m["name"]), m.get("config", {}))
            for m in manifest_modules if m.get("config")]

    if not tabs:
        log.warning("No modules with config found")
        return False

    # ── Tab buttons (row at top) ──────────────────────────────────────

    tab_btn_width = min(70, (_DLG_WIDTH - 2 * _MARGIN) // len(tabs))
    for i, (mod_name, desc, _cfg) in enumerate(tabs):
        btn_name = "tab_%s" % mod_name
        btn = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlButtonModel")
        btn.Name = btn_name
        btn.Label = _pretty_name(mod_name)
        btn.PositionX = _MARGIN + i * tab_btn_width
        btn.PositionY = _MARGIN
        btn.Width = tab_btn_width - 2
        btn.Height = _TAB_HEIGHT - 4
        dlg_model.insertByName(btn_name, btn)

    # ── Config fields per tab ─────────────────────────────────────────

    field_controls = {}  # "module.key" -> control_name
    field_schemas = {}   # "module.key" -> schema dict
    tab_controls = {}    # module_name -> list of control names

    content_y = _MARGIN + _TAB_HEIGHT + 4

    for mod_name, desc, config in tabs:
        tab_ctrl_names = []
        y = content_y

        for field_name, schema in config.items():
            full_key = "%s.%s" % (mod_name, field_name)
            widget = schema.get("widget", "text")
            label_text = schema.get("label", field_name)

            # Label
            lbl_name = "lbl_%s_%s" % (mod_name, field_name)
            lbl = dlg_model.createInstance(
                "com.sun.star.awt.UnoControlFixedTextModel")
            lbl.Name = lbl_name
            lbl.Label = label_text
            lbl.PositionX = _MARGIN
            lbl.PositionY = y + 2
            lbl.Width = _LABEL_WIDTH
            lbl.Height = _ROW_HEIGHT
            dlg_model.insertByName(lbl_name, lbl)
            tab_ctrl_names.append(lbl_name)

            # Widget
            ctrl_name = "fld_%s_%s" % (mod_name, field_name)

            if widget == "checkbox":
                ctrl = _make_checkbox(dlg_model, ctx, ctrl_name, y)
            elif widget == "password":
                ctrl = _make_text(dlg_model, ctx, ctrl_name, y, echo_char=42)
            elif widget == "textarea":
                ctrl = _make_textarea(dlg_model, ctx, ctrl_name, y)
                y += _ROW_HEIGHT  # textarea takes extra space
            elif widget == "number" or widget == "slider":
                ctrl = _make_numeric(dlg_model, ctx, ctrl_name, y, schema)
            elif widget == "select":
                ctrl = _make_listbox(dlg_model, ctx, ctrl_name, y, schema)
            elif widget == "file" or widget == "folder":
                ctrl = _make_file(dlg_model, ctx, ctrl_name, y, mod_name, field_name)
                tab_ctrl_names.append("btn_%s_%s" % (mod_name, field_name))
            else:
                ctrl = _make_text(dlg_model, ctx, ctrl_name, y)

            dlg_model.insertByName(ctrl_name, ctrl)
            tab_ctrl_names.append(ctrl_name)
            field_controls[full_key] = ctrl_name
            field_schemas[full_key] = schema

            y += _ROW_HEIGHT + _ROW_GAP

        tab_controls[mod_name] = tab_ctrl_names

    # ── OK / Cancel buttons ───────────────────────────────────────────

    ok_btn = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlButtonModel")
    ok_btn.Name = "btn_ok"
    ok_btn.Label = "OK"
    ok_btn.PositionX = _DLG_WIDTH - 2 * 60 - _MARGIN - 6
    ok_btn.PositionY = _DLG_HEIGHT - 26
    ok_btn.Width = 60
    ok_btn.Height = 20
    ok_btn.PushButtonType = 1  # OK
    ok_btn.DefaultButton = True
    dlg_model.insertByName("btn_ok", ok_btn)

    cancel_btn = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.Name = "btn_cancel"
    cancel_btn.Label = "Cancel"
    cancel_btn.PositionX = _DLG_WIDTH - 60 - _MARGIN
    cancel_btn.PositionY = _DLG_HEIGHT - 26
    cancel_btn.Width = 60
    cancel_btn.Height = 20
    cancel_btn.PushButtonType = 2  # CANCEL
    dlg_model.insertByName("btn_cancel", cancel_btn)

    # ── Create dialog ─────────────────────────────────────────────────

    dialog = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dlg_model)

    toolkit = smgr.createInstanceWithContext(
        "com.sun.star.awt.Toolkit", ctx)
    dialog.setVisible(False)
    dialog.createPeer(toolkit, None)

    # ── Populate values ───────────────────────────────────────────────

    _populate_values(dialog, field_controls, field_schemas, config_service)

    # ── Tab switching ─────────────────────────────────────────────────

    active_tab = [tabs[0][0]]

    def switch_tab(mod_name):
        active_tab[0] = mod_name
        for tab_mod, ctrl_names in tab_controls.items():
            visible = (tab_mod == mod_name)
            for cn in ctrl_names:
                try:
                    c = dialog.getControl(cn)
                    if c:
                        c.setVisible(visible)
                except Exception:
                    pass

    # Wire tab buttons
    import unohelper
    from com.sun.star.awt import XActionListener

    class _TabListener(unohelper.Base, XActionListener):
        def __init__(self, target_mod):
            self._mod = target_mod

        def actionPerformed(self, evt):
            switch_tab(self._mod)

        def disposing(self, evt):
            pass

    for mod_name, _desc, _cfg in tabs:
        btn_ctrl = dialog.getControl("tab_%s" % mod_name)
        if btn_ctrl:
            btn_ctrl.addActionListener(_TabListener(mod_name))

    # Show first tab, hide others
    switch_tab(active_tab[0])

    # ── Execute ───────────────────────────────────────────────────────

    result = dialog.execute()

    if result == 1:  # OK
        _save_values(dialog, field_controls, field_schemas, config_service)
        dialog.dispose()
        return True

    dialog.dispose()
    return False


# ── Widget factory helpers ────────────────────────────────────────────


def _make_checkbox(dlg_model, ctx, name, y):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlCheckBoxModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH
    ctrl.Height = _ROW_HEIGHT
    return ctrl


def _make_text(dlg_model, ctx, name, y, echo_char=0):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlEditModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH
    ctrl.Height = _ROW_HEIGHT
    if echo_char:
        ctrl.EchoChar = echo_char
    return ctrl


def _make_textarea(dlg_model, ctx, name, y):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlEditModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH
    ctrl.Height = _ROW_HEIGHT * 3
    ctrl.MultiLine = True
    ctrl.VScroll = True
    return ctrl


def _make_numeric(dlg_model, ctx, name, y, schema):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlNumericFieldModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH
    ctrl.Height = _ROW_HEIGHT
    ctrl.Spin = True
    if "min" in schema:
        ctrl.ValueMin = float(schema["min"])
    if "max" in schema:
        ctrl.ValueMax = float(schema["max"])
    if "step" in schema:
        ctrl.ValueStep = float(schema["step"])
    else:
        ctrl.ValueStep = 1.0
    if schema.get("type") == "float":
        ctrl.DecimalDigits = 1
    else:
        ctrl.DecimalDigits = 0
    return ctrl


def _make_listbox(dlg_model, ctx, name, y, schema):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlListBoxModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH
    ctrl.Height = _ROW_HEIGHT
    ctrl.Dropdown = True
    options = schema.get("options", [])
    if options:
        labels = tuple(o.get("label", o.get("value", "")) for o in options)
        ctrl.StringItemList = labels
    return ctrl


def _make_file(dlg_model, ctx, name, y, mod_name, field_name):
    ctrl = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlEditModel")
    ctrl.Name = name
    ctrl.PositionX = _FIELD_X
    ctrl.PositionY = y
    ctrl.Width = _FIELD_WIDTH - _BROWSE_BTN_WIDTH - 4
    ctrl.Height = _ROW_HEIGHT

    # Browse button
    btn = dlg_model.createInstance(
        "com.sun.star.awt.UnoControlButtonModel")
    btn_name = "btn_%s_%s" % (mod_name, field_name)
    btn.Name = btn_name
    btn.Label = "..."
    btn.PositionX = _FIELD_X + _FIELD_WIDTH - _BROWSE_BTN_WIDTH
    btn.PositionY = y
    btn.Width = _BROWSE_BTN_WIDTH
    btn.Height = _ROW_HEIGHT
    dlg_model.insertByName(btn_name, btn)

    return ctrl


# ── Populate / Save ───────────────────────────────────────────────────


def _populate_values(dialog, field_controls, field_schemas, config_service):
    """Load current config values into dialog controls."""
    for full_key, ctrl_name in field_controls.items():
        schema = field_schemas[full_key]
        widget = schema.get("widget", "text")

        # Read current value (no access control for settings dialog)
        val = config_service.get(full_key)
        if val is None:
            val = schema.get("default")

        ctrl = dialog.getControl(ctrl_name)
        if ctrl is None:
            continue

        try:
            if widget == "checkbox":
                ctrl.getModel().State = 1 if val else 0
            elif widget in ("text", "password", "file", "folder"):
                ctrl.getModel().Text = str(val) if val else ""
            elif widget == "textarea":
                ctrl.getModel().Text = str(val) if val else ""
            elif widget in ("number", "slider"):
                ctrl.getModel().Value = float(val) if val is not None else 0
            elif widget == "select":
                options = schema.get("options", [])
                values = [o.get("value", "") for o in options]
                if val in values:
                    idx = values.index(val)
                    ctrl.selectItemPos(idx, True)
                elif options:
                    ctrl.selectItemPos(0, True)
        except Exception:
            log.exception("Error populating %s", full_key)


def _save_values(dialog, field_controls, field_schemas, config_service):
    """Read dialog controls and save to config."""
    for full_key, ctrl_name in field_controls.items():
        schema = field_schemas[full_key]
        widget = schema.get("widget", "text")
        field_type = schema.get("type", "string")

        ctrl = dialog.getControl(ctrl_name)
        if ctrl is None:
            continue

        try:
            if widget == "checkbox":
                val = ctrl.getModel().State == 1
            elif widget in ("text", "password", "textarea", "file", "folder"):
                val = ctrl.getModel().Text or ""
            elif widget in ("number", "slider"):
                raw = ctrl.getModel().Value
                if field_type == "int":
                    val = int(raw)
                else:
                    val = float(raw)
            elif widget == "select":
                options = schema.get("options", [])
                sel = ctrl.getSelectedItemPos()
                if 0 <= sel < len(options):
                    val = options[sel].get("value", "")
                else:
                    val = schema.get("default", "")
            else:
                val = ctrl.getModel().Text or ""

            config_service.set(full_key, val)

        except Exception:
            log.exception("Error saving %s", full_key)


# ── Utilities ─────────────────────────────────────────────────────────


def _pretty_name(module_name):
    """Convert module_name to a pretty tab label."""
    return module_name.replace("_", " ").title()
