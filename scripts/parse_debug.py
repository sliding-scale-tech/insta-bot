import re
from pathlib import Path

for name in ["01_after_load.html", "02_explore_hashtag.html"]:
    html = Path("debug_output", name).read_text(encoding="utf-8", errors="ignore")
    print(f"\n=== {name} ===")
    patterns = [
        "Continue",
        "Password",
        "Log in",
        "Add a comment",
        'aria-label="Comment"',
        'name="password"',
        'type="password"',
        "explore/tags",
        "accounts/login",
    ]
    for pat in patterns:
        print(f"  {pat}: {html.count(pat)}")

    # extract visible-ish text snippets
    for m in re.finditer(r">(Continue|Password|Log in|Add a comment[^<]{0,30})<", html):
        print("  text:", m.group(1)[:80])
