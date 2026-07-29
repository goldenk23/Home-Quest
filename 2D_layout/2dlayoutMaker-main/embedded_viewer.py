"""Persistent WebView2 host for the in-app Home Quest 3D preview."""

from __future__ import annotations

import ctypes
import json
import os
import queue
import sys
import threading
import tkinter as tk
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable


class _ReadOnlyStaticHandler(SimpleHTTPRequestHandler):
    """Serve packaged viewer assets without exposing a writable endpoint."""

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _deny_write(self) -> None:
        self.send_error(405, "Viewer asset server is read-only")

    do_POST = do_PUT = do_PATCH = do_DELETE = _deny_write

    def list_directory(self, _path: str):
        self.send_error(404, "Directory listing is disabled")
        return None


def _find_viewer_dist() -> Path:
    app_dir = Path(__file__).resolve().parent
    candidates = [
        Path(getattr(sys, "_MEIPASS", app_dir)) / "dist",
        app_dir / "viewer_dist",
        app_dir.parents[1] / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    raise FileNotFoundError(
        "Home Quest 3D build assets were not found. Run 'npm run build' in the "
        "Home Quest folder, or package dist as viewer_dist beside the Python editor."
    )


def _load_webview2_binding():
    """Load the one pinned tkwebview2/pywebview pair with its known API rename."""
    try:
        versions = (version("tkwebview2"), version("pywebview"))
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Embedded 3D support is not installed. Run "
            "'pip install -r requirements.txt' for the Python editor."
        ) from exc
    if versions != ("3.5.0", "5.4"):
        raise RuntimeError(
            "Unsupported embedded-viewer package versions "
            f"(tkwebview2 {versions[0]}, pywebview {versions[1]}). "
            "Reinstall the pinned Python requirements."
        )

    # ponytail: tkwebview2 has no stable public adapter API; constrain this one-field
    # bridge to the pinned pair and replace the host package if another API mismatch appears.
    from webview.platforms.edgechromium import EdgeChrome

    if not hasattr(EdgeChrome, "web_view"):
        EdgeChrome.web_view = property(lambda adapter: adapter.webview)

    from tkwebview2.tkwebview2 import WebView2, have_runtime

    return WebView2, have_runtime


class EmbeddedViewerRuntime:
    """Own one loopback server and one child WebView2 for the app lifetime."""

    def __init__(
        self,
        root: tk.Misc,
        host: tk.Frame,
        on_refresh_requested: Callable[[], None],
    ) -> None:
        self.root = root
        self.host = host
        self.on_refresh_requested = on_refresh_requested
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._webview = None
        self._core = None
        self._viewer_url: str | None = None
        self._web_message_handler = self._on_web_message
        self._process_failed_handler = self._on_process_failed
        self._pywebview_message_handler = None
        self._ready = False
        self._active = False
        self._closed = False
        self._request_id = 0
        self._latest_message: dict[str, Any] | None = None
        self._events: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        self._poll_after_id: str | None = None
        self._core_after_id: str | None = None
        self._ole_initialized = False

        self._failure = tk.Frame(host, bg="#111827")
        self._failure_message = tk.Label(
            self._failure,
            text="Open the 3D Viewer tab to start the preview.",
            bg="#111827",
            fg="#e5e7eb",
            justify="center",
            wraplength=620,
            padx=28,
            pady=20,
        )
        self._failure_message.pack(expand=True)
        self._retry = tk.Button(self._failure, text="Retry 3D Viewer", command=self.retry)
        self._retry.pack(pady=(0, 24))
        self._failure.pack(fill="both", expand=True)
        self._poll_after_id = self.root.after(50, self._poll_events)

    def _start_server(self) -> str:
        if self._server is not None:
            host, port = self._server.server_address[:2]
            return f"http://{host}:{port}/?embedded=1"

        dist = _find_viewer_dist()
        handler = partial(_ReadOnlyStaticHandler, directory=os.fspath(dist))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name="viewer-assets", daemon=True)
        thread.start()
        self._server = server
        self._server_thread = thread
        host, port = server.server_address[:2]
        return f"http://{host}:{port}/?embedded=1"

    def _initialize_sta(self) -> None:
        if self._ole_initialized:
            return
        ole32 = ctypes.windll.ole32
        ole32.CoInitializeEx.restype = ctypes.c_long
        result = ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
        if result not in (0, 1):
            raise RuntimeError(
                "WebView2 requires a Windows STA UI thread; restart VastuCraft Pro and retry."
            )
        self._ole_initialized = True

    def start(self) -> None:
        if self._closed or self._webview is not None:
            return
        try:
            self._viewer_url = self._start_server()
            self._initialize_sta()
            WebView2, have_runtime = _load_webview2_binding()
            if not have_runtime():
                raise RuntimeError(
                    "Microsoft Edge WebView2 Runtime is required. Install the Evergreen "
                    "WebView2 Runtime, then click Retry 3D Viewer."
                )

            self._hide_failure()
            self.host.update_idletasks()
            self._webview = WebView2(
                self.host,
                max(self.host.winfo_width(), 320),
                max(self.host.winfo_height(), 240),
                url="",
                bd=0,
                highlightthickness=0,
            )
            self._webview.pack(fill="both", expand=True)
            self._wait_for_core()
        except Exception as exc:
            self._dispose_browser()
            self._show_failure(str(exc))

    def _wait_for_core(self) -> None:
        if self._closed or self._webview is None:
            return
        core = getattr(self._webview, "core", None)
        if core is None:
            self._core_after_id = self.root.after(50, self._wait_for_core)
            return
        self._core_after_id = None
        self._core = core
        try:
            # pywebview's RPC listener expects array messages; this viewer owns an object-based
            # bridge, so remove that listener before the React page starts posting messages.
            adapter = getattr(self._webview, "web_view", None)
            native_web = getattr(self._webview, "web", None)
            if adapter is not None and native_web is not None:
                self._pywebview_message_handler = adapter.on_script_notify
                native_web.WebMessageReceived -= self._pywebview_message_handler

            core.Settings.AreDevToolsEnabled = False
            core.Settings.AreDefaultContextMenusEnabled = False
            core.WebMessageReceived += self._web_message_handler
            core.ProcessFailed += self._process_failed_handler
            if not self._viewer_url:
                raise RuntimeError("The local 3D viewer address is unavailable")
            core.Navigate(self._viewer_url)
        except Exception as exc:
            self._events.put({"type": "_process-failed", "error": str(exc)})

    def _on_web_message(self, _sender: Any, args: Any) -> None:
        try:
            raw_message = getattr(args, "WebMessageAsJson", None)
            if raw_message is None:
                raw_message = args.get_WebMessageAsJson()
            message = json.loads(str(raw_message))
            if isinstance(message, dict):
                self._events.put(message)
        except Exception:
            return

    def _on_process_failed(self, _sender: Any, args: Any) -> None:
        reason = getattr(args, "ProcessFailedKind", "unknown failure")
        self._events.put({"type": "_process-failed", "error": str(reason)})

    def _poll_events(self) -> None:
        if self._closed:
            return
        try:
            while True:
                message = self._events.get_nowait()
                message_type = message.get("type")
                if message_type == "ready":
                    self._ready = True
                    if self._active and self._latest_message is not None:
                        self._post(self._latest_message)
                elif message_type == "refresh-request":
                    self.on_refresh_requested()
                elif message_type == "_process-failed":
                    self._dispose_browser()
                    self._show_failure(
                        "The 3D render process stopped unexpectedly "
                        f"({message.get('error', 'unknown reason')}). Click Retry to restore it."
                    )
        except queue.Empty:
            pass
        self._poll_after_id = self.root.after(50, self._poll_events)

    def send_layout(self, layout: dict[str, Any]) -> None:
        self._active = True
        self._request_id += 1
        self._latest_message = {
            "type": "load-layout",
            "requestId": self._request_id,
            "payloadJson": json.dumps(layout, ensure_ascii=False, separators=(",", ":")),
        }
        self.start()
        if self._ready:
            self._post(self._latest_message)

    def send_host_error(self, error: str) -> None:
        if self._ready:
            self._post({"type": "host-error", "error": error})
        else:
            self._show_failure(error)

    def deactivate(self) -> None:
        self._active = False
        if self._ready:
            self._post({"type": "deactivate"})

    def _post(self, message: dict[str, Any]) -> None:
        if self._core is None:
            return
        try:
            self._core.PostWebMessageAsJson(json.dumps(message, ensure_ascii=False))
        except Exception as exc:
            self._dispose_browser()
            self._show_failure(f"Could not communicate with the 3D viewer: {exc}")

    def retry(self) -> None:
        if self._closed:
            return
        self._dispose_browser()
        self.start()

    def _hide_failure(self) -> None:
        try:
            self._failure.pack_forget()
        except tk.TclError:
            pass

    def _show_failure(self, message: str) -> None:
        if self._closed:
            return
        self._failure_message.configure(text=message)
        self._failure.pack(fill="both", expand=True)
        self._failure.lift()

    def _dispose_browser(self) -> None:
        self._ready = False
        core, self._core = self._core, None
        if core is not None:
            try:
                core.WebMessageReceived -= self._web_message_handler
            except Exception:
                pass
            try:
                core.ProcessFailed -= self._process_failed_handler
            except Exception:
                pass
        if self._core_after_id is not None:
            try:
                self.root.after_cancel(self._core_after_id)
            except Exception:
                pass
            self._core_after_id = None
        webview, self._webview = self._webview, None
        self._pywebview_message_handler = None
        if webview is not None:
            synthetic_window = getattr(webview, "window", None)
            try:
                webview.destroy()
            except Exception:
                try:
                    webview.web.Dispose()
                except Exception:
                    pass
            try:
                from tkwebview2 import tkwebview2 as binding

                if synthetic_window in binding.windows:
                    binding.windows.remove(synthetic_window)
            except Exception:
                pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None
        self._dispose_browser()
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        if self._server_thread is not None:
            self._server_thread.join(timeout=1)
            self._server_thread = None
        if self._ole_initialized:
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass
            self._ole_initialized = False
