# pyright: reportMissingImports=false

"""Textual presentation for a verified Capstone Thread projection.

The app owns terminal layout and focus only. Snapshot, event cursor, command
identity, and command admission remain owned by the caller's Thread adapter.
This first vertical slice intentionally accepts a synchronous submit callback;
the production HTTP/SSE adapter can bridge it from an async transport later.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Select, Static

from .thread_commands import ThreadCommandFactory
from .thread_protocol import CommandReceipt, EventPage, ThreadSnapshot


ModelOption = tuple[str, str]
SubmitCommand = Callable[[dict[str, Any]], CommandReceipt]


def _model_label(model_id: str) -> str:
    return {"ieee39": "IEEE-39", "pypsa39": "PyPSA-39"}.get(model_id, model_id)


def _event_line(event: Any) -> str:
    event_type = getattr(event, "event_type", "event")
    event_seq = getattr(event, "event_seq", "?")
    payload = getattr(event, "payload", {})
    authority = payload.get("authority_label") if isinstance(payload, dict) else None
    suffix = f" · {authority}" if isinstance(authority, str) and authority else ""
    return f"#{event_seq}  {event_type}{suffix}"


class ThreadTuiApp(App[None]):
    """Two-column Thread workspace backed by one verified snapshot/page."""

    CSS = """
    Screen { background: #081216; color: #d9e9e3; }
    Header { background: #0b181c; color: #9fe4d3; }
    Footer { background: #0b181c; color: #8fa9a6; }
    #workspace { height: 1fr; layout: horizontal; }
    #grid-pane, #thread-pane { width: 1fr; height: 1fr; padding: 1 2; border: solid #28464a; }
    #grid-pane { border-left: none; }
    #thread-pane { border-right: none; }
    .eyebrow { color: #6ea098; text-style: bold; }
    .panel-title { color: #eff7f1; text-style: bold; margin: 1 0; }
    .model-card, .state-card { padding: 1; margin: 0 0 1 0; background: #102328; border: solid #31534f; }
    #grid-page { height: 1fr; min-height: 8; padding: 2; color: #9bd7c7; background: #0b1c20; border: solid #28464b; content-align: center middle; }
    #model-select { margin: 0 0 1 0; }
    #command-input { height: 5; margin: 1 0; }
    #events-log { height: 1fr; min-height: 8; border: solid #28464a; background: #0f2023; }
    .button-row { height: auto; layout: horizontal; }
    .button-row Button { margin: 0 1 0 0; }
    #feedback { height: 2; color: #b8ebdc; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
    ]

    def __init__(
        self,
        snapshot: ThreadSnapshot,
        events: EventPage,
        submit_command: SubmitCommand,
        *,
        model_options: Sequence[ModelOption] = (("ieee39", "IEEE-39 · pandapower"),),
    ) -> None:
        super().__init__()
        if events.thread_id != snapshot.thread_id:
            raise ValueError("Thread event page does not match snapshot")
        if events.after_event_seq != snapshot.last_event_seq:
            raise ValueError("Thread event page does not follow snapshot cursor")
        if not model_options:
            raise ValueError("model_options must not be empty")
        option_ids = {model_id for model_id, _ in model_options}
        if snapshot.active_model_context.model_id not in option_ids:
            raise ValueError("active model is not present in model_options")
        self.snapshot = snapshot
        self.events = events
        self.submit_command = submit_command
        self.model_options = tuple(model_options)
        self._command_number = 0

    def compose(self) -> ComposeResult:
        model = self.snapshot.active_model_context
        yield Header(show_clock=False)
        with Horizontal(id="workspace"):
            with Vertical(id="grid-pane"):
                yield Static("MODEL / CURRENT GRID", classes="eyebrow")
                yield Static("电网模型", classes="panel-title")
                yield Static(
                    f"{_model_label(model.model_id)}\n"
                    f"{model.implementation_family} · revision {model.model_revision}\n"
                    f"Context {model.id} · selection {model.selection_revision}",
                    id="model-status", classes="model-card",
                )
                yield Select(
                    tuple((label, model_id) for model_id, label in self.model_options),
                    value=model.model_id, allow_blank=False,
                    id="model-select", prompt="选择目标模型",
                )
                yield Static(
                    f"当前页\n{self.snapshot.active_grid_page_id}\n\n"
                    "电网图投影\nUnicode/ANSI",
                    id="grid-page",
                )
                with Horizontal(classes="button-row"):
                    yield Button("切换模型", id="switch-model", variant="default")
            with Vertical(id="thread-pane"):
                yield Static(f"THREAD / RUN {self.snapshot.run.run_id}", classes="eyebrow")
                yield Static("对话 Thread", classes="panel-title")
                yield Static(
                    f"连接 · live\nRun · {self.snapshot.run.state}\nCursor · #{self.snapshot.last_event_seq}",
                    id="state-status", classes="state-card",
                )
                yield RichLog(id="events-log", markup=False, wrap=True)
                yield Input(placeholder="围绕当前电网模型输入指令…", id="command-input")
                with Horizontal(classes="button-row"):
                    yield Button("发送普通指令", id="send-ordinary", variant="default")
                    yield Button("发送专业请求", id="send-professional", variant="primary")
                yield Static("", id="feedback")
        yield Footer()

    def on_mount(self) -> None:
        event_log = self.query_one("#events-log", RichLog)
        if self.events.events:
            for event in self.events.events:
                event_log.write(_event_line(event))
        else:
            event_log.write("暂无公开事件 · 等待当前 Thread")
        self._refresh_controls()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-input":
            self._submit_message("send_professional")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "switch-model":
            self._submit_model_switch()
        elif event.button.id == "send-ordinary":
            self._submit_message("send_ordinary")
        elif event.button.id == "send-professional":
            self._submit_message("send_professional")

    def _refresh_controls(self) -> None:
        blocked = self.snapshot.current_attempt is not None or (
            self.snapshot.pending_model_switch is not None
            or self.snapshot.pending_selection is not None
        )
        historical = False
        self.query_one("#send-ordinary", Button).disabled = blocked or historical
        self.query_one("#send-professional", Button).disabled = blocked or historical
        self.query_one("#switch-model", Button).disabled = blocked or historical

    def _factory(self) -> ThreadCommandFactory:
        self._command_number += 1
        return ThreadCommandFactory(self.snapshot.thread_id, self.snapshot.run.run_id)

    def _identity(self, prefix: str) -> dict[str, str]:
        suffix = str(self._command_number)
        return {
            "command_id": f"cmd_tui_{prefix}_{suffix}",
            "idempotency_key": f"idem_tui_{prefix}_{suffix}",
        }

    def _submit_message(self, kind: str) -> None:
        input_widget = self.query_one("#command-input", Input)
        text = input_widget.value.strip()
        if not text:
            self.query_one("#feedback", Static).update("请输入指令后再提交")
            return
        factory = self._factory()
        identity = self._identity(kind)
        builder = factory.send_ordinary if kind == "send_ordinary" else factory.send_professional
        command = builder(
            text, expected_event_seq=self.snapshot.last_event_seq, **identity,
        )
        self._submit(command, input_widget)

    def _submit_model_switch(self) -> None:
        value = self.query_one("#model-select", Select).value
        if not isinstance(value, str):
            self.query_one("#feedback", Static).update("请选择目标模型")
            return
        if value == self.snapshot.active_model_context.model_id:
            self.query_one("#feedback", Static).update("目标模型已经是当前模型")
            return
        factory = self._factory()
        command = factory.switch_model(
            value, expected_event_seq=self.snapshot.last_event_seq,
            **self._identity("switch_model"),
        )
        self._submit(command, None)

    def _submit(self, command: dict[str, Any], input_widget: Input | None) -> None:
        try:
            receipt = self.submit_command(command)
        except Exception as error:  # UI boundary renders a bounded failure only.
            self.query_one("#feedback", Static).update(f"命令失败 · {type(error).__name__}")
            return
        status = receipt.status
        suffix = f" · {receipt.rejection}" if receipt.rejection else ""
        self.query_one("#feedback", Static).update(f"{command['kind']} · {status}{suffix}")
        if input_widget is not None and status == "accepted":
            input_widget.value = ""


def run_tui(
    snapshot: ThreadSnapshot,
    events: EventPage,
    submit_command: SubmitCommand,
    *,
    model_options: Sequence[ModelOption] = (("ieee39", "IEEE-39 · pandapower"),),
) -> None:
    """Run the Textual workspace for an already connected Thread adapter."""

    ThreadTuiApp(
        snapshot, events, submit_command, model_options=model_options,
    ).run()


__all__ = ["ModelOption", "SubmitCommand", "ThreadTuiApp", "run_tui"]
