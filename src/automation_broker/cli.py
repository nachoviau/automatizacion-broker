import argparse
import json
from typing import Any, Dict, List

from .parsers.allianz_auto import parse_allianz_auto
from .fillers.absanet import AbsaNetForm, load_mapping


def main() -> None:
    parser = argparse.ArgumentParser(prog="absa-automation", description="Parser Allianz Auto PDF y llenado AbsaNet")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parsear PDF de Allianz Auto")
    parse_cmd.add_argument("--pdf", required=True, help="Ruta al PDF a procesar")
    parse_cmd.add_argument("--out", required=False, help="Ruta al JSON de salida")

    fill_cmd = subparsers.add_parser("fill", help="Construir plan de llenado desde un JSON y mapping YAML (dry-run)")
    fill_cmd.add_argument("--json", required=True, help="Ruta al JSON de datos (salida del parser)")
    fill_cmd.add_argument("--yaml", required=True, help="Ruta al YAML de selectores")

    live_cmd = subparsers.add_parser(
        "fill-live",
        help="Abrir Firefox, esperar el formulario de Alta y llenar (sin submit)",
    )
    live_cmd.add_argument("--json", required=True, help="Ruta al JSON de datos (salida del parser)")
    live_cmd.add_argument("--yaml", required=True, help="Ruta al YAML de selectores")
    live_cmd.add_argument("--url", required=True, help="URL del sitio (home tras login)")
    live_cmd.add_argument(
        "--url-pattern",
        default="/Poliza/Alta/",
        help="Fragmento de URL que identifica la página de alta (default: /Poliza/Alta/)",
    )
    live_cmd.add_argument(
        "--wait-any",
        required=False,
        help="Lista separada por comas de selectores CSS/ID para disparar al primero que aparezca, ej: #idAseguradora,#Moneda,#TipoVigencia,#idProductor",
    )
    live_cmd.add_argument(
        "--tabs",
        default="condiciones",
        help="Lista separada por comas de tabs a llenar (default: condiciones)",
    )
    live_cmd.add_argument(
        "--sel-timeout",
        type=int,
        default=5,
        help="Timeout (s) para localizar elementos individuales (default: 5)",
    )

    args = parser.parse_args()

    if args.command == "parse":
        data, missing = parse_allianz_auto(args.pdf)
        payload = {"data": data.to_dict(), "missing": missing}
        output = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Escrito JSON en {args.out}")
        else:
            print(output)
        return

    if args.command == "fill":
        with open(args.json, "r", encoding="utf-8") as f:
            payload: Dict[str, Any] = json.load(f)
        data_dict: Dict[str, Any] = payload.get("data", payload)
        mapping = load_mapping(args.yaml)

        from .models import PolicyData
        pd = PolicyData(**data_dict)
        dummy = AbsaNetForm.__new__(AbsaNetForm)  # type: ignore
        plan = AbsaNetForm.build_fill_plan(dummy, pd, mapping)  # type: ignore
        for field_key, action, value in plan:
            sel = action["selector"]
            print(f"{field_key}: {value} -> {sel}")
        return

    if args.command == "fill-live":
        with open(args.json, "r", encoding="utf-8") as f:
            payload: Dict[str, Any] = json.load(f)
        data_dict: Dict[str, Any] = payload.get("data", payload)
        mapping = load_mapping(args.yaml)
        from .models import PolicyData
        pd = PolicyData(**data_dict)

        # WebDriver (Firefox) con autodetección de binario (Snap/apt)
        import os
        import shutil
        import time
        from selenium import webdriver
        from selenium.common.exceptions import InvalidArgumentException, WebDriverException
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.common.by import By

        opts = FirefoxOptions()
        if os.environ.get("HEADLESS") == "1":
            opts.add_argument("-headless")

        def try_launch(firefox_bin: str | None):
            if firefox_bin:
                opts.binary_location = firefox_bin
            else:
                try:
                    del opts.binary_location  # type: ignore[attr-defined]
                except Exception:
                    pass
            return webdriver.Firefox(options=opts)

        driver = None
        last_error: Exception | None = None
        candidates: list[str | None] = []
        env_bin = os.environ.get("FIREFOX_BIN")
        if env_bin:
            candidates.append(env_bin)
        candidates.append(None)
        candidates.append("/usr/lib/firefox/firefox")
        candidates.append("/snap/firefox/current/usr/lib/firefox/firefox")
        which_ff = shutil.which("firefox")
        if which_ff and not which_ff.endswith("/snap/bin/firefox"):
            candidates.append(which_ff)

        for cand in candidates:
            try:
                driver = try_launch(cand)
                break
            except (InvalidArgumentException, WebDriverException) as e:
                last_error = e
                continue

        if driver is None:
            raise RuntimeError(
                f"No se pudo iniciar Firefox. Setea FIREFOX_BIN con la ruta real del binario (e.g. /usr/lib/firefox/firefox). Último error: {last_error}"
            )

        driver.maximize_window()
        try:
            # 1) Ir al sitio y esperar navegación manual a la URL de alta
            driver.get(args.url)
            print(f"[nav] Esperando navegación a URL que contenga '{args.url_pattern}'…")
            while True:
                if args.url_pattern in driver.current_url:
                    print(f"[nav] Detectada URL de alta: {driver.current_url}")
                    break
                time.sleep(0.02)

            # 2) Esperar que el formulario esté listo: primer selector disponible
            default_targets = ["#idAseguradora", "#Moneda", "#TipoVigencia", "#idProductor"]
            wait_targets: List[str] = (
                [s.strip() for s in args.wait_any.split(",") if s.strip()]
                if args.wait_any
                else default_targets
            )

            def present(sel: str) -> bool:
                try:
                    css = sel if sel.startswith("#") or sel.startswith("[") or " " in sel else f"#{sel}"
                    el = driver.find_element(By.CSS_SELECTOR, css)
                    return el.is_displayed()
                except Exception:
                    return False

            print(f"[ready] Esperando cualquiera de: {', '.join(wait_targets)}")
            while True:
                if any(present(sel) for sel in wait_targets):
                    break
                time.sleep(0.02)

            # 3) Llenado (solo tabs solicitadas)
            allowed_tabs = {t.strip() for t in args.tabs.split(',') if t.strip()}
            print(f"[fill] start (tabs: {', '.join(sorted(allowed_tabs))})")
            form = AbsaNetForm(driver, timeout=int(args.sel_timeout))
            
            # Mostrar siempre las tres vistas en el panel (navegables con ◀ ▶)
            try:
                form.show_preview_condiciones_dict(data_dict)
                form.show_preview_item_dict(data_dict)
                form.show_preview_costos(data_dict)
            except Exception:
                pass
            
            logs: List[str] = []
            if 'condiciones' in allowed_tabs:
                plan = form.build_fill_plan(pd, mapping)
                plan = [step for step in plan if step[1].get('tab') == 'condiciones']
                logs.extend(form.fill_from_plan(plan, mapping, dry_run=False))
            
            if 'items_modal' in allowed_tabs:
                # Mostrar preview del item apenas abra el modal (moverlo al método del modal para timing exacto)
                logs.extend(form.fill_items_modal(pd))
            
            if 'costos_preview' in allowed_tabs:
                try:
                    form.show_preview_costos(data_dict)
                except Exception:
                    pass
            
            for l in logs:
                print(l)
            print("[fill] end")
        finally:
            # Dejar el navegador abierto para revisión manual
            pass
        return


if __name__ == "__main__":
    main()
