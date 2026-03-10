import flet as ft
from scanner import scan_all, is_market_open
from symbols import NIFTY50, NIFTY100, NIFTY200
import time
import threading
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"ema9": 9, "ema21": 21, "scan_interval": 5}


def main(page: ft.Page):
    page.title = "NIFTY EMA Scanner"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0d1b2a"
    page.padding = ft.padding.only(left=16, right=16, top=12, bottom=16)
    page.scroll = ft.ScrollMode.ADAPTIVE

    cfg = load_config()
    _scan_thread: threading.Thread | None = None
    _auto_timer:  threading.Timer   | None = None

    # ── Signal cards list ────────────────────────────────────────────────────
    results_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    status_text = ft.Text(
        "Ready — press Scan to start",
        color=ft.Colors.GREY_400,
        size=13,
    )

    market_chip = ft.Chip(
        label=ft.Text("Checking market…", size=12),
        bgcolor=ft.Colors.GREY_800,
    )

    def _update_market_status():
        if is_market_open():
            market_chip.label = ft.Text("🟢 Market OPEN", size=12, color=ft.Colors.GREEN_300)
            market_chip.bgcolor = ft.Colors.GREEN_900
        else:
            market_chip.label = ft.Text("🔴 Market CLOSED", size=12, color=ft.Colors.RED_300)
            market_chip.bgcolor = ft.Colors.RED_900
        page.update()

    _update_market_status()

    # ── List dropdown ────────────────────────────────────────────────────────
    list_dropdown = ft.Dropdown(
        label="Stock Universe",
        options=[
            ft.dropdown.Option("NIFTY50"),
            ft.dropdown.Option("NIFTY100"),
            ft.dropdown.Option("NIFTY200"),
        ],
        value="NIFTY50",
        width=180,
        text_size=14,
    )

    progress_ring = ft.ProgressRing(visible=False, width=22, height=22, stroke_width=2)

    buy_badge  = ft.Text("BUY: 0",  color=ft.Colors.GREEN_300,  weight=ft.FontWeight.BOLD)
    sell_badge = ft.Text("SELL: 0", color=ft.Colors.RED_300,    weight=ft.FontWeight.BOLD)

    # ── Do the scan ──────────────────────────────────────────────────────────
    def _do_scan(e=None):
        nonlocal _auto_timer

        # Cancel existing auto-timer
        if _auto_timer and _auto_timer.is_alive():
            _auto_timer.cancel()

        scan_btn.disabled = True
        auto_btn.disabled = True
        progress_ring.visible = True
        status_text.value = f"Scanning {list_dropdown.value}…"
        results_col.controls.clear()
        buy_badge.value  = "BUY: —"
        sell_badge.value = "SELL: —"
        page.update()

        sym_map = {"NIFTY50": NIFTY50, "NIFTY100": NIFTY100, "NIFTY200": NIFTY200}
        symbols = sym_map.get(list_dropdown.value, NIFTY50)

        t0      = time.time()
        results = scan_all(symbols, cfg)
        elapsed = round(time.time() - t0, 1)

        buy_count  = sum(1 for r in results if r["Signal Type"] == "BUY")
        sell_count = len(results) - buy_count

        buy_badge.value  = f"BUY: {buy_count}"
        sell_badge.value = f"SELL: {sell_count}"
        status_text.value = (
            f"Done in {elapsed}s  •  {len(results)} signal(s)  •  "
            f"{time.strftime('%H:%M:%S')}"
        )

        results_col.controls.clear()

        if not results:
            results_col.controls.append(
                ft.Container(
                    content=ft.Text("No signals found at this time.", color=ft.Colors.GREY_500, size=14),
                    alignment=ft.alignment.center, padding=30,
                )
            )
        else:
            for res in results:
                is_buy  = res["Signal Type"] == "BUY"
                sig_clr = ft.Colors.GREEN_400 if is_buy else ft.Colors.RED_400
                sig_bg  = "#1b3a2e" if is_buy else "#3a1b1b"

                ema_fast_key = next((k for k in res if k.startswith("EMA") and k != "EMA21"), "EMA9")
                ema_slow_key = next((k for k in res if k.startswith("EMA") and k != "EMA9"), "EMA21")

                card = ft.Card(
                    elevation=6,
                    color=sig_bg,
                    content=ft.Container(
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column([
                            ft.Row([
                                ft.Text(res["Stock Symbol"], size=18, weight=ft.FontWeight.BOLD),
                                ft.Container(
                                    content=ft.Text(res["Signal Type"], color=ft.Colors.WHITE,
                                                    weight=ft.FontWeight.BOLD, size=13),
                                    bgcolor=sig_clr,
                                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                                    border_radius=20,
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Divider(height=8, color="#2a3a4a"),
                            ft.Row([
                                _info("Price",   f"₹{res['Current Price']}"),
                                _info("SL",      f"₹{res.get('Stop Loss','—')}"),
                                _info("Target",  f"₹{res.get('Target','—')}"),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                _info(ema_fast_key, str(res.get(ema_fast_key, '—'))),
                                _info(ema_slow_key, str(res.get(ema_slow_key, '—'))),
                                _info("Volume",  f"{res.get('Volume',0):,}"),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(res["Signal Time"], size=11, color=ft.Colors.GREY_500),
                        ], spacing=6),
                    ),
                )
                results_col.controls.append(card)

        scan_btn.disabled = False
        auto_btn.disabled = False
        progress_ring.visible = False
        _update_market_status()
        page.update()

        # Schedule next auto-scan
        interval_sec = int(cfg.get("scan_interval", 5)) * 60
        _auto_timer = threading.Timer(interval_sec, _do_scan)
        _auto_timer.daemon = True
        _auto_timer.start()

    def _start_scan_thread(e=None):
        t = threading.Thread(target=_do_scan, daemon=True)
        t.start()

    scan_btn = ft.ElevatedButton(
        text="Scan Now",
        icon=ft.Icons.SEARCH,
        on_click=_start_scan_thread,
        bgcolor=ft.Colors.BLUE_700,
        color=ft.Colors.WHITE,
        height=44,
    )

    auto_btn = ft.OutlinedButton(
        text="Auto ON",
        icon=ft.Icons.AUTORENEW,
        on_click=_start_scan_thread,
        height=44,
    )

    # ── Layout ───────────────────────────────────────────────────────────────
    page.add(
        ft.SafeArea(
            ft.Column([
                # Header
                ft.Row([
                    ft.Text("📈 NIFTY EMA Scanner", size=22, weight=ft.FontWeight.BOLD),
                    market_chip,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                # Controls
                ft.Row([
                    list_dropdown,
                    scan_btn,
                    auto_btn,
                    progress_ring,
                ], spacing=10, alignment=ft.MainAxisAlignment.START),

                # Status + badges
                ft.Row([status_text, buy_badge, sell_badge], spacing=16),

                ft.Divider(color="#1e2d3d"),

                # Signal cards
                ft.Container(results_col, expand=True, height=580),
            ], spacing=12)
        )
    )


def _info(label: str, value: str) -> ft.Column:
    return ft.Column([
        ft.Text(label, size=11, color=ft.Colors.GREY_500),
        ft.Text(value,  size=13, weight=ft.FontWeight.W_600),
    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


if __name__ == "__main__":
    ft.app(target=main)
