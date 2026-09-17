from bcra_rag.domain.freeze import dump_date, freeze_footer, names_freeze


def test_footer_uses_date_prefix() -> None:
    assert freeze_footer("2026-09-01T00:00:00+00:00", "A8307") == (
        "Según el dump del 2026-09-01 (texto ordenado al A8307)."
    )
    assert freeze_footer(None, None) == (
        "Según el dump del desconocido (texto ordenado al desconocido)."
    )


def test_names_freeze_accepts_iso_or_date() -> None:
    iso = "2026-09-01T00:00:00+00:00"
    assert names_freeze(f"x {iso} A8307", iso, "A8307")
    assert names_freeze("Según el dump del 2026-09-01 (texto ordenado al A8307).", iso, "A8307")
    assert not names_freeze("sin fechas", iso, "A8307")
    assert dump_date("raro") == "raro"
