# Chat with Document - Sidebar Panel implementation
# Follows the working pattern from LibreOffice's Python ToolPanel example:
# XUIElement wrapper creates panel in getRealInterface() via ContainerWindowProvider + XDL.

import os
import uno
import unohelper

from com.sun.star.ui import XUIElementFactory, XUIElement, XToolPanel, XSidebarPanel
from com.sun.star.ui.UIElementType import TOOLPANEL
from com.sun.star.awt import XActionListener

# Extension ID from description.xml; XDL path inside the .oxt
EXTENSION_ID = "org.extension.localwriter"
XDL_PATH = "LocalWriterDialogs/ChatPanelDialog.xdl"


def _debug_log(ctx, msg):
    """Write one line to debug log (user config dir, ~/localwriter_chat_debug.log, /tmp)."""
    for path in _debug_log_paths(ctx):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            return
        except Exception:
            continue


def _debug_log_paths(ctx):
    out = []
    try:
        path_settings = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.util.PathSettings", ctx)
        user_config = getattr(path_settings, "UserConfig", "")
        if user_config and str(user_config).startswith("file://"):
            user_config = str(uno.fileUrlToSystemPath(user_config))
            out.append(os.path.join(user_config, "localwriter_chat_debug.log"))
    except Exception:
        pass
    out.append(os.path.expanduser("~/localwriter_chat_debug.log"))
    out.append("/tmp/localwriter_chat_debug.log")
    return out


def _get_arg(args, name):
    """Extract PropertyValue from args by Name."""
    for pv in args:
        if hasattr(pv, "Name") and pv.Name == name:
            return pv.Value
    return None


class SendButtonListener(unohelper.Base, XActionListener):
    """Listener for the Send button - runs chat with document, updates response area."""

    def __init__(self, ctx, frame, query_control, response_control):
        self.ctx = ctx
        self.frame = frame
        self.query_control = query_control
        self.response_control = response_control

    def actionPerformed(self, evt):
        try:
            query_text = ""
            if self.query_control and self.query_control.getModel():
                query_text = (self.query_control.getModel().Text or "").strip()
            if not query_text:
                from main import MainJob
                job = MainJob(self.ctx)
                query_text = job.input_box("Ask a question about your document:", "Chat with Document", "").strip()
            if not query_text:
                return

            from main import MainJob
            job = MainJob(self.ctx)
            model = None
            if self.frame:
                try:
                    model = self.frame.getController().getModel()
                except Exception:
                    pass
            if not model:
                desktop = job.ctx.getServiceManager().createInstanceWithContext(
                    "com.sun.star.frame.Desktop", job.ctx)
                model = desktop.getCurrentComponent()
            if not model or not hasattr(model, "getText"):
                job.show_error("No document open.", "Chat with Document")
                return

            max_context = int(job.get_config("chat_context_length", 8000))
            doc_text = job.get_full_document_text(model, max_context)
            if not doc_text.strip():
                job.show_error("Document is empty.", "Chat with Document")
                return

            prompt = "Document content:\n\n%s\n\nUser question: %s" % (doc_text, query_text)
            system_prompt = job.get_config("chat_system_prompt",
                "You are a helpful assistant. Answer the user's question based on the document content provided.")
            max_tokens = int(job.get_config("chat_max_tokens", 512))
            api_type = str(job.get_config("api_type", "completions")).lower()

            doc_cursor = None
            if not (self.response_control and self.response_control.getModel()):
                try:
                    text = model.getText()
                    doc_cursor = text.createTextCursor()
                    doc_cursor.gotoEnd(False)
                    doc_cursor.insertString("\n\n--- Chat response ---\n\n", False)
                except Exception:
                    pass

            def append_chunk(chunk_text):
                if self.response_control and self.response_control.getModel():
                    current = self.response_control.getModel().Text or ""
                    self.response_control.getModel().Text = current + chunk_text
                elif doc_cursor is not None:
                    doc_cursor.insertString(chunk_text, False)

            job.stream_completion(prompt, system_prompt, max_tokens, api_type, append_chunk)

            if self.query_control and self.query_control.getModel():
                self.query_control.getModel().Text = ""
        except Exception as e:
            try:
                from main import MainJob
                job = MainJob(self.ctx)
                job.show_error(str(e), "Chat with Document")
            except Exception:
                pass

    def disposing(self, evt):
        pass


class ChatToolPanel(unohelper.Base, XToolPanel, XSidebarPanel):
    """Holds the panel window; implements XToolPanel and XSidebarPanel."""

    def __init__(self, panel_window, ctx):
        self.ctx = ctx
        self.PanelWindow = panel_window
        self.Window = panel_window

    def getWindow(self):
        return self.Window

    def createAccessible(self, parent_accessible):
        return self.PanelWindow

    def getHeightForWidth(self, width):
        return uno.createUnoStruct("com.sun.star.ui.LayoutSize", 280, -1, 280)

    def getMinimalWidth(self):
        return 180


class ChatPanelElement(unohelper.Base, XUIElement):
    """XUIElement wrapper; creates panel window in getRealInterface() via ContainerWindowProvider."""

    def __init__(self, ctx, frame, parent_window, resource_url):
        self.ctx = ctx
        self.xFrame = frame
        self.xParentWindow = parent_window
        self.ResourceURL = resource_url
        self.Frame = frame
        self.Type = TOOLPANEL
        self.toolpanel = None
        self.m_panelRootWindow = None

    def getRealInterface(self):
        _debug_log(self.ctx, "getRealInterface called")
        if not self.toolpanel:
            try:
                root_window = self._getOrCreatePanelRootWindow()
                _debug_log(self.ctx, "root_window created: %s" % (root_window is not None))
                self.toolpanel = ChatToolPanel(root_window, self.ctx)
                self._wireSendButton(root_window)
            except Exception as e:
                _debug_log(self.ctx, "getRealInterface ERROR: %s" % e)
                import traceback
                _debug_log(self.ctx, traceback.format_exc())
                raise
        return self.toolpanel

    def _getOrCreatePanelRootWindow(self):
        _debug_log(self.ctx, "_getOrCreatePanelRootWindow entered")
        pip = self.ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation(EXTENSION_ID)
        dialog_url = base_url + "/" + XDL_PATH
        _debug_log(self.ctx, "dialog_url: %s" % dialog_url)
        provider = self.ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.ContainerWindowProvider", self.ctx)
        _debug_log(self.ctx, "calling createContainerWindow...")
        self.m_panelRootWindow = provider.createContainerWindow(
            dialog_url, "", self.xParentWindow, None)
        _debug_log(self.ctx, "createContainerWindow returned")
        # Sidebar does not show the panel content without this (framework does not make it visible).
        if self.m_panelRootWindow and hasattr(self.m_panelRootWindow, "setVisible"):
            self.m_panelRootWindow.setVisible(True)
        return self.m_panelRootWindow

    def _wireSendButton(self, root_window):
        """Attach SendButtonListener to the send button. root_window may support XControlContainer."""
        try:
            if hasattr(root_window, "getControl"):
                send_btn = root_window.getControl("send")
                query_ctrl = root_window.getControl("query")
                response_ctrl = root_window.getControl("response")
                send_btn.addActionListener(SendButtonListener(
                    self.ctx, self.xFrame, query_ctrl, response_ctrl))
                _debug_log(self.ctx, "Send button wired")
        except Exception as e:
            _debug_log(self.ctx, "_wireSendButton: %s" % e)
            pass


class ChatPanelFactory(unohelper.Base, XUIElementFactory):
    """Factory that creates ChatPanelElement instances for the sidebar."""

    def __init__(self, ctx):
        self.ctx = ctx

    def createUIElement(self, resource_url, args):
        _debug_log(self.ctx, "createUIElement: %s" % resource_url)
        if "ChatPanel" not in resource_url:
            from com.sun.star.container import NoSuchElementException
            raise NoSuchElementException("Unknown resource: " + resource_url)

        frame = _get_arg(args, "Frame")
        parent_window = _get_arg(args, "ParentWindow")
        _debug_log(self.ctx, "ParentWindow: %s" % (parent_window is not None))
        if not parent_window:
            from com.sun.star.lang import IllegalArgumentException
            raise IllegalArgumentException("ParentWindow is required")

        return ChatPanelElement(self.ctx, frame, parent_window, resource_url)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ChatPanelFactory,
    "org.extension.localwriter.ChatPanelFactory",
    ("com.sun.star.ui.UIElementFactory",),
)
