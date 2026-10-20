"""Windows-only background subscriber. No browser or GUI needs to stay open."""

import argparse
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from notify import DEFAULT_URL, SERVICE, request_json


AUMID = "AOPC.Notify"
log = logging.getLogger("aopc-notify")


def state_directory(base_url):
    key = hashlib.sha256(base_url.encode()).hexdigest()[:12]
    return Path(os.environ["LOCALAPPDATA"]) / "AOPCNotify" / key


def save_state(path, instance, last_id):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"instance": instance, "last_id": last_id}), encoding="utf-8")
    temporary.replace(path)


def load_state(path, health):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if (state["instance"] == health["instance"] and type(state["last_id"]) is int
                and 0 <= state["last_id"] <= health["last_id"]):
            return state["last_id"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # A first installation subscribes to new messages, without replaying history.
    return health["last_id"]


def build_toast(item, base_url):
    from windows_toasts import Toast, ToastButton

    url = f'{base_url}/messages/{item["id"]}'
    toast = Toast(
        text_fields=["新消息", item["message"][:240]],
        launch_action=url,
    )
    # Re-delivery after a crash updates the same notification instead of duplicating it.
    toast.tag = str(item["id"])
    toast.group = "inbox"
    toast.AddAction(ToastButton("查看全文", launch=url))
    toast.on_failed = lambda event: log.error("Windows rejected message %s: %s", item["id"], event)
    return toast


def create_toaster():
    import winreg
    from windows_toasts import InteractableWindowsToaster
    from winrt.windows.ui.notifications import NotificationSetting

    # Per-user identity: no administrator access or custom URI handler required.
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "AOPC Notify")
    toaster = InteractableWindowsToaster("AOPC Notify", notifierAUMID=AUMID)
    try:
        setting = toaster.toastNotifier.setting
    except OSError as error:
        # Some Windows 10 builds cannot query a newly registered desktop identity,
        # even though show() and notification-center history already work.
        if error.winerror != -2147023728:
            raise
        setting = NotificationSetting.ENABLED
    if setting != NotificationSetting.ENABLED:
        raise RuntimeError("Windows notifications are disabled for AOPC Notify; enable them in Settings")
    return toaster


class DesktopSession:
    """A per-URL Windows mutex and stop event; handles close when the process exits."""

    def __init__(self, key):
        import ctypes
        from ctypes import wintypes

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, arguments in {
            "CreateMutexW": [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR],
            "CreateEventW": [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR],
            "OpenEventW": [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR],
        }.items():
            function = getattr(self.kernel, name)
            function.argtypes = arguments
            function.restype = wintypes.HANDLE
        self.kernel.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.event_name = f"Local\\AOPCNotifyStop-{key}"
        self.mutex_name = f"Local\\AOPCNotify-{key}"
        self.mutex = None
        self.event = None

    def acquire(self):
        import ctypes

        self.mutex = self.kernel.CreateMutexW(None, False, self.mutex_name)
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.close()
            return False
        self.event = self.kernel.CreateEventW(None, True, False, self.event_name)
        if not self.event:
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def wait(self, seconds=0):
        return self.kernel.WaitForSingleObject(self.event, int(seconds * 1000)) == 0

    def stop(self):
        handle = self.kernel.OpenEventW(0x0002, False, self.event_name)
        if handle:
            try:
                self.kernel.SetEvent(handle)
            finally:
                self.kernel.CloseHandle(handle)

    def close(self):
        for handle in (self.event, self.mutex):
            if handle:
                self.kernel.CloseHandle(handle)
        self.event = self.mutex = None


def run(base_url, directory, session):
    toaster = create_toaster()
    state_path = directory / "cursor.json"
    instance = None
    cursor = 0
    log.info("Bridge started for %s", base_url)
    while not session.wait():
        try:
            health = request_json("/health", base_url=base_url)
            if health.get("service") != SERVICE:
                raise RuntimeError("The target is not an AOPC Notify v2 service")
            if instance != health["instance"]:
                cursor = load_state(state_path, health)
                instance = health["instance"]
                save_state(state_path, instance, cursor)
            batch = request_json(f"/api/events?after={cursor}&wait=25", base_url=base_url, timeout=30)
            if batch["instance"] != instance:
                instance = None
                continue
            for item in batch["messages"]:
                if session.wait():
                    break
                toaster.show_toast(build_toast(item, base_url))
                cursor = item["id"]
                save_state(state_path, instance, cursor)
                log.info("Toast accepted by Windows: message %s", cursor)
        except Exception:
            log.exception("Notification bridge will retry in 5 seconds")
            session.wait(5)
    log.info("Bridge stopped")


def main():
    parser = argparse.ArgumentParser(description="Windows notifications for the AOPC inbox")
    parser.add_argument("--url", default=os.environ.get("AOPC_NOTIFY_URL", DEFAULT_URL))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--background", action="store_true")
    modes.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("the notification bridge must run in the logged-in Windows desktop session")
    base_url = args.url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.query or parsed.fragment:
        parser.error("--url must be an HTTP(S) service URL")
    directory = state_directory(base_url)
    directory.mkdir(parents=True, exist_ok=True)
    session = DesktopSession(directory.name)
    if args.stop:
        session.stop()
        print("Stop requested (up to 30 seconds).")
        return
    if args.background:
        executable = Path(sys.executable).with_name("pythonw.exe")
        subprocess.Popen(
            [str(executable), str(Path(__file__).resolve()), "--url", base_url],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                           | subprocess.CREATE_BREAKAWAY_FROM_JOB), close_fds=True,
        )
        print(f"Background bridge requested. Logs: {directory / 'bridge.log'}")
        return
    handler = RotatingFileHandler(directory / "bridge.log", maxBytes=256_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    if not session.acquire():
        log.info("Bridge already running")
        return
    try:
        run(base_url, directory, session)
    except Exception:
        log.exception("Bridge could not start")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
