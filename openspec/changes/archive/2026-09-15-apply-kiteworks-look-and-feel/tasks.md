## 1. assistant-ui chrome

- [x] 1.1 In `observatory.css`: navy `:root` (`#050821`, `#121548`, `#f4b223`, `#425cc7`, `#b5c5e8`, `color-scheme: dark`, `--radius-lg: 8px`); solid navy body (no radial glow); delete `body::after` grid; drop `backdrop-filter`; panel `border-radius: 8px`; navy footer with light type; retint hardcoded bubbles/pills/chips/secondary/abstain; primary and `.observatory-pill` stay `999px` pills with flat gold Enviar. Keep `content: "Citas"`, `content: "Guardrails"`, `12rem`, icon-button hide, thought-group, layout-user. Verify `uv run pytest tests/test_ui.py::test_observatory_css_tokens -q` after 1.3

- [x] 1.2 In `theme.py`: `THEME_COLOR` `#050821`; navy fill constants; flat `PRIMARY_FILL` `#f4b223`; `block_radius="8px"`; `primary_hue` amber, `secondary_hue` blue; keep Sora; `.set()` both default and `_dark` keys; keep `classList.add("dark")`. Verify `uv run pytest tests/test_ui.py::test_observatory_theme_helpers -q` after 1.3

- [x] 1.3 In `tests/test_ui.py`, retarget CSS/theme assertions to `#f4b223`, `#425cc7`, `#121548`, `#050821`, `color-scheme: dark`, `8px`; drop `#04111d`, `#72d6cb`; assert no `backdrop-filter` and no `body::after` grid. Keep Citas/Guardrails, 12rem, thought-group, layout-user, JS `dark` class. Verify `uv run pytest tests/test_ui.py -q`

- [x] 1.4 Run `uv run pytest tests/test_ui.py -q` then `uv run pytest -q --cov=src` (src coverage >= 80%), `uv run ruff check .`, `uv run mypy src`. Do not run live-server, prod smoke, or paid L1

- [x] 1.5 Browser-use MCP: screenshot the Kiteworks reference; serve the observatory; check logged-out 1280×720 (Pregunta+Enviar on first screen, navy page, gold Enviar) and 375×812 (Enviar/Limpiar one row); toggle Staff/Usuario; click a canned pill. Fix CSS if teal glow, dark bubbles, or Gradio gray remain. Do not restyle OTP/favicon unless the main screen is already right
