"""Sandboxed workspace file tools callable by the LLM.

Every path is resolved and verified to stay inside `workspace_root` before
any read/write happens — this is the one place a prompt-injected or
malicious LLM response could try to escape the sandbox (e.g. "../../etc/passwd"),
so path containment is checked on every call, not just at startup.
"""

from pathlib import Path

from . import metrics


class WorkspaceError(Exception):
    pass


class WorkspaceTools:
    def __init__(self, root: str, max_file_bytes: int, allowed_tools: set[str]):
        self.root = Path(root).resolve()
        self.max_file_bytes = max_file_bytes
        self.allowed_tools = allowed_tools
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise WorkspaceError(f"path escapes workspace sandbox: {relative_path!r}")
        return candidate

    def _check_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise WorkspaceError(f"tool not in allowlist: {tool_name!r}")

    def list_workspace_files(self) -> list[str]:
        self._check_allowed("list_workspace_files")
        metrics.log_tool_call("list_workspace_files")
        return sorted(
            str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()
        )

    def read_workspace_file(self, relative_path: str) -> str:
        self._check_allowed("read_workspace_file")
        metrics.log_tool_call("read_workspace_file")
        path = self._resolve(relative_path)
        if not path.is_file():
            raise WorkspaceError(f"no such file: {relative_path!r}")
        return path.read_text(encoding="utf-8", errors="replace")

    def write_workspace_file(self, relative_path: str, content: str) -> None:
        self._check_allowed("write_workspace_file")
        metrics.log_tool_call("write_workspace_file")
        if len(content.encode("utf-8")) > self.max_file_bytes:
            raise WorkspaceError("content exceeds max_file_bytes limit")
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
