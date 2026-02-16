# Debugging Report: Model Selection ComboBox Dropdown

We attempted to implement a "Recently Used Models" dropdown in the Settings dialog using a LibreOffice `ComboBox` (LRU history). However, the dropdown arrow and menu failed to display correctly on the user's Linux environment.

## What Was Attempted

1.  **XDL Definition**:
    *   Changed `dlg:textfield` to `dlg:combobox`.
    *   Added `dlg:dropdown="true"` and `dlg:border="1"`.
2.  **Height Adjustments**:
    *   **Standard (14)**: Arrow was missing.
    *   **Large (80)**: Dropdown menu was permanently expanded, consuming the entire dialog space.
    *   **Intermediate (16, 18)**: Attempted to find a "sweet spot" where the arrow rendered but the list stayed collapsed.
3.  **Python Logic ([main.py](file:///home/keithcu/Desktop/Python/localwriter/main.py))**:
    *   Explicitly setting `Dropdown = True` and `DropDown = True`.
    *   Setting `LineCount = 10` for the dropdown list length.
    *   Setting `Border = 1` to force 3D rendering (common GTK trick).
    *   Setting `NativeWidget = False` to bypass GTK theme rendering in favor of internal UNO rendering.
    *   Applying properties both before and after `addItems()`.

## Learnings & Observations

*   **Linux VCL Backend**: Rendering of `ComboBox` is highly dependent on the VCL backend (`gtk3`, `kf5`, `gen`) and the system GTK theme.
*   **Property Sensitivity**: UNO properties are case-sensitive. `Dropdown` is the standard, but some versions/contexts use `DropDown`.
*   **Height Quirk**: In some UNO versions, the `height` attribute in XDL for a dropdown ComboBox must include the room for the dropped-down list, while in others it should only be the height of the single-line edit field.

## Next Steps to Consider

*   **Switch to ListBox**: In UNO, a `ListBox` with `Dropdown=True` can often behave like a ComboBox. It might have better rendering support on Linux.
*   **Dynamic Creation**: Try creating the control programmatically via the `ServiceManager` instead of defining it in the static [.xdl](file:///home/keithcu/Desktop/Python/localwriter/LocalWriterDialogs/SettingsDialog.xdl) file. This allows for more granular control over initialization.
*   **Focus Trick**: In some themes, the dropdown arrow only appears when the control has focus or when the mouse hovers over it.
*   **Check VCL Plugin**: Verify which VCL plugin is being used (`SAL_USE_VCLPLUGIN`) as some (like `gtk3`) are known to have rendering bugs with specific themes.

> [!TIP]
> If a standard `ComboBox` remains broken, a fallback could be a `ListBox` for selection + a "Custom..." button that opens a simple text input dialog.
