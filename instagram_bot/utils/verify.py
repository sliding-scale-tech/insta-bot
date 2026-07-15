"""Save verification screenshots + JSON for each tool check."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instagram_bot.config.settings import TOOL_CHECKS_DIR


def _run_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = TOOL_CHECKS_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


class ToolVerifier:
    """Record pass/fail for each tool with screenshot evidence."""

    def __init__(self) -> None:
        self.run_dir = _run_dir()
        self.results: list[dict[str, Any]] = []
        self.step = 0

    def record(
        self,
        page,
        name: str,
        success: bool,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.step += 1
        prefix = f"{self.step:02d}_{name}"
        png = self.run_dir / f"{prefix}.png"
        meta = self.run_dir / f"{prefix}.json"

        try:
            page.screenshot(path=str(png), full_page=True)
        except Exception as screenshot_error:
            png = None
            error = error or str(screenshot_error)

        entry = {
            "step": self.step,
            "name": name,
            "success": success,
            "url": getattr(page, "url", ""),
            "detail": detail or {},
            "error": error,
            "screenshot": str(png) if png else None,
        }
        self.results.append(entry)
        meta.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}" + (f" — {error}" if error else ""))
        if png:
            print(f"         screenshot: {png.name}")

    def write_report(self) -> Path:
        passed = sum(1 for r in self.results if r["success"])
        total = len(self.results)
        report = {
            "summary": {
                "passed": passed,
                "failed": total - passed,
                "total": total,
                "run_dir": str(self.run_dir),
            },
            "results": self.results,
        }
        report_path = self.run_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        html_lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>Tool Check Report</title>",
            "<style>body{font-family:sans-serif;margin:24px}",
            ".pass{color:green}.fail{color:red}img{max-width:900px;border:1px solid #ccc;margin:8px 0}",
            "pre{background:#f5f5f5;padding:12px;overflow:auto}</style></head><body>",
            f"<h1>Tool Checks: {passed}/{total} passed</h1>",
            f"<p>Run folder: {self.run_dir}</p>",
        ]
        for item in self.results:
            cls = "pass" if item["success"] else "fail"
            html_lines.append(
                f"<h2 class='{cls}'>{item['step']:02d}. {item['name']} — "
                f"{'PASS' if item['success'] else 'FAIL'}</h2>"
            )
            if item.get("error"):
                html_lines.append(f"<p><strong>Error:</strong> {item['error']}</p>")
            if item.get("detail"):
                html_lines.append(
                    f"<pre>{json.dumps(item['detail'], indent=2)}</pre>"
                )
            if item.get("screenshot"):
                html_lines.append(
                    f"<img src='{Path(item['screenshot']).name}' alt='{item['name']}'>"
                )
        html_lines.append("</body></html>")
        html_path = self.run_dir / "report.html"
        html_path.write_text("\n".join(html_lines), encoding="utf-8")

        print(f"\nReport saved:")
        print(f"  {report_path}")
        print(f"  {html_path}")
        return html_path
