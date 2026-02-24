"""Logging for LocalWriter.

Two systems:
1. Standard ``logging`` — setup_logging() configures the ``localwriter`` logger
   hierarchy with a FileHandler to ~/localwriter.log.  All modules that call
   ``logging.getLogger("localwriter.xxx")`` inherit this handler automatically.

2. Legacy file-based debug_log / agent_log / watchdog used by aihordeclient.
   Kept for backward compatibility.
"""

import logging
import os
import sys
import json
import time
import traceback
import threading

# ── Standard logging setup ─────────────────────────────────────────────

LOG_PATH = os.path.join(os.path.expanduser("~"), "localwriter.log")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

_setup_done = False


def setup_logging(level="DEBUG"):
    """Configure the ``localwriter`` logger hierarchy.

    Forces a FileHandler on the ``localwriter`` logger (not root),
    so it works regardless of root logger state set by other extensions.
    Truncates the log file on startup (mode ``"w"``) for clean sessions.

    No-op if the logger already has handlers (e.g. set up inline by main.py).
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    logger = logging.getLogger("localwriter")
    if logger.handlers:
        return

    logger.propagate = False

    handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)

    numeric = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(numeric)


def set_log_level(level):
    """Change the ``localwriter`` logger level at runtime."""
    logger = logging.getLogger("localwriter")
    numeric = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(numeric)


# ── Legacy file-based logging (aihordeclient) ──────────────────────────

_debug_log_path = None
_agent_log_path = None
_enable_agent_log = False
_init_lock = threading.Lock()
_exception_hooks_installed = False

# Watchdog shared state
_activity_state = {"phase": "", "round_num": -1, "tool_name": None, "last_activity": 0.0}
_activity_lock = threading.Lock()
_watchdog_started = False
_watchdog_interval_sec = 15
_watchdog_threshold_sec = 30

DEBUG_LOG_FILENAME = "localwriter_debug.log"
AGENT_LOG_FILENAME = "localwriter_agent.log"
FALLBACK_DEBUG = os.path.join(os.path.expanduser("~"), "localwriter_debug.log")
FALLBACK_AGENT = os.path.join(os.path.expanduser("~"), "localwriter_agent.log")


def init_logging(ctx):
    """Set global log paths. Idempotent; safe to call from any entry point."""
    global _debug_log_path, _agent_log_path, _enable_agent_log
    with _init_lock:
        if _debug_log_path is not None:
            return
        _debug_log_path = FALLBACK_DEBUG
        _agent_log_path = FALLBACK_AGENT
        _enable_agent_log = False
        try:
            from plugin.modules.core.services.config import _user_config_dir
            udir = _user_config_dir(ctx)
            if udir:
                _debug_log_path = os.path.join(udir, DEBUG_LOG_FILENAME)
                _agent_log_path = os.path.join(udir, AGENT_LOG_FILENAME)
        except Exception:
            pass

        _install_global_exception_hooks()


def _user_config_dir_fallback(ctx):
    """Fallback if config service isn't available yet."""
    try:
        import uno
        ps = ctx.getValueByName(
            "/singletons/com.sun.star.util.thePathSettings"
        )
        return uno.fileUrlToSystemPath(ps.UserConfig)
    except Exception:
        return None


def _get_debug_path():
    return _debug_log_path if _debug_log_path else FALLBACK_DEBUG


def _get_agent_path():
    return _agent_log_path if _agent_log_path else FALLBACK_AGENT


def _install_global_exception_hooks():
    """Install sys.excepthook and threading.excepthook. Idempotent."""
    global _exception_hooks_installed
    if _exception_hooks_installed:
        return
    _exception_hooks_installed = True

    _original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        try:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            debug_log("Unhandled exception:\n" + "".join(tb_lines).strip(),
                      context="Excepthook")
        except Exception:
            pass
        try:
            _original(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _hook

    if getattr(threading, "excepthook", None) is not None:
        _orig_t = threading.excepthook

        def _thook(args):
            try:
                msg = "Unhandled exception in thread %s: %s\n%s" % (
                    getattr(args, "thread", None),
                    getattr(args, "exc_type", args),
                    "".join(traceback.format_exception(
                        args.exc_type, args.exc_value, args.exc_traceback
                    )) if getattr(args, "exc_type", None) else "",
                )
                debug_log(msg.strip(), context="Excepthook")
            except Exception:
                pass
            try:
                if _orig_t:
                    _orig_t(args)
            except Exception:
                pass

        threading.excepthook = _thook


def log_exception(ex, context="AIHorde"):
    """Log an exception with traceback to the debug log."""
    try:
        tb = getattr(ex, "__traceback__", None)
        if tb is not None:
            tb_lines = traceback.format_exception(type(ex), ex, tb)
            msg = "".join(tb_lines).strip()
        else:
            msg = str(ex)
        debug_log(msg, context=context)
    except Exception:
        debug_log(str(ex), context=context)


def debug_log(msg, context=None):
    """Write one line to the debug log. Uses global path (set by init_logging)."""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        ms = int((time.time() % 1) * 1000)
        prefix = "[%s] " % context if context else ""
        line = "%s.%03d | %s%s\n" % (now, ms, prefix, msg)
    except Exception:
        line = msg + "\n"
    path = _get_debug_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def agent_log(location, message, data=None, hypothesis_id=None, run_id=None):
    """Write one NDJSON line to agent log if enabled."""
    if not _enable_agent_log:
        return
    payload = {"location": location, "message": message,
               "timestamp": int(time.time() * 1000)}
    if data is not None:
        payload["data"] = data
    if hypothesis_id is not None:
        payload["hypothesisId"] = hypothesis_id
    if run_id is not None:
        payload["runId"] = run_id
    line = json.dumps(payload) + "\n"
    path = _get_agent_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def update_activity_state(phase, round_num=None, tool_name=None):
    """Update shared activity state for the watchdog."""
    with _activity_lock:
        _activity_state["phase"] = phase
        _activity_state["last_activity"] = time.monotonic()
        if round_num is not None:
            _activity_state["round_num"] = round_num
        if tool_name is not None:
            _activity_state["tool_name"] = tool_name


def _watchdog_loop(status_control):
    """Daemon thread: detect hangs and update UI status."""
    while True:
        time.sleep(_watchdog_interval_sec)
        with _activity_lock:
            phase = _activity_state["phase"]
            round_num = _activity_state["round_num"]
            tool_name = _activity_state["tool_name"]
            last = _activity_state["last_activity"]
        if not phase:
            continue
        elapsed = time.monotonic() - last
        if elapsed < _watchdog_threshold_sec:
            continue
        msg = "WATCHDOG: no activity for %ds; phase=%s round=%s tool=%s" % (
            int(elapsed), phase, round_num, tool_name or "")
        debug_log(msg, context="Chat")
        if status_control:
            try:
                hung_text = "Hung: %s round %s" % (phase, round_num)
                if tool_name:
                    hung_text += " %s" % tool_name
                status_control.setText(hung_text)
            except Exception:
                pass


def start_watchdog_thread(ctx, status_control=None):
    """Start the hang-detection watchdog (idempotent)."""
    global _watchdog_started
    with _activity_lock:
        if _watchdog_started:
            return
        _watchdog_started = True
    t = threading.Thread(target=_watchdog_loop, args=(status_control,),
                         daemon=True)
    t.start()
