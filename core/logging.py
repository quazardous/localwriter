"""Simple file logging for LocalWriter."""
import os
import json
import time

# Agent/debug log paths (tried in order)
def _agent_log_paths():
    """Paths for agent NDJSON log. Tries workspace .cursor first, then user dir."""
    out = []
    try:
        ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out.append(os.path.join(ext_dir, ".cursor", "debug.log"))
    except Exception:
        pass
    out.append(os.path.expanduser("~/localwriter_agent_debug.log"))
    out.append("/tmp/localwriter_agent_debug.log")
    return out


def agent_log(location, message, data=None, hypothesis_id=None, run_id=None):
    """Write one NDJSON line to agent debug log."""
    payload = {"location": location, "message": message, "timestamp": int(time.time() * 1000)}
    if data is not None:
        payload["data"] = data
    if hypothesis_id is not None:
        payload["hypothesisId"] = hypothesis_id
    if run_id is not None:
        payload["runId"] = run_id
    line = json.dumps(payload) + "\n"
    for path in _agent_log_paths():
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            return
        except Exception:
            continue


def debug_log_paths(ctx):
    """Paths for chat debug log (user config dir, ~, /tmp)."""
    import uno
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


def debug_log(ctx, msg):
    """Write one line to chat debug log."""
    for path in debug_log_paths(ctx):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            return
        except Exception:
            continue


def log_to_file(message):
    try:
        import datetime
        home = os.path.expanduser("~")
        log_path = os.path.join(home, "log.txt")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("%s - %s\n" % (now, message))
    except Exception:
        pass
