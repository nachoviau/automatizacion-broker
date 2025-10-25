from typing import Any, Dict, List, Tuple
import unicodedata
import yaml
import time

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

from ..models import PolicyData


DEFAULT_TIMEOUT = 20


def _by_from_string(s: str) -> str:
    s = s.lower()
    return {
        "id": By.ID,
        "css": By.CSS_SELECTOR,
        "xpath": By.XPATH,
        "name": By.NAME,
    }.get(s, By.CSS_SELECTOR)


def _normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _js_select_by_text_or_value(driver: WebDriver, select_el, target: Any) -> bool:
    script = r"""
    const sel = arguments[0];
    const targetRaw = arguments[1];
    const normalize = s => (s ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
    const tgt = normalize(String(targetRaw));
    let matchIndex = -1;
    for (let i = 0; i < sel.options.length; i++) {
      const opt = sel.options[i];
      if (normalize(opt.text) === tgt || normalize(opt.value) === tgt) { matchIndex = i; break; }
    }
    if (matchIndex < 0) {
      for (let i = 0; i < sel.options.length; i++) {
        const opt = sel.options[i];
        if (normalize(opt.text).includes(tgt) || normalize(opt.value).includes(tgt)) { matchIndex = i; break; }
      }
    }
    if (matchIndex >= 0) {
      sel.selectedIndex = matchIndex;
      sel.dispatchEvent(new Event('input', { bubbles: true }));
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
    return false;
    """
    try:
        return bool(driver.execute_script(script, select_el, str(target)))
    except Exception:
        return False


def _select_by_visible_text_tolerant(select: Select, value: Any) -> None:
    target_text = str(value)
    try:
        select.select_by_visible_text(target_text)
        return
    except Exception:
        pass
    normalized_target = _normalize_text(target_text)
    for idx, option in enumerate(select.options):
        if _normalize_text(option.text) == normalized_target or _normalize_text(option.get_attribute("value")) == normalized_target:
            select.select_by_index(idx)
            return
    for idx, option in enumerate(select.options):
        if normalized_target in _normalize_text(option.text) or normalized_target in _normalize_text(option.get_attribute("value")):
            select.select_by_index(idx)
            return
    raise ValueError(f"No option matched value '{target_text}'")


def _close_any_select2(driver: WebDriver, wait: WebDriverWait) -> None:
    try:
        search = driver.find_elements(By.CSS_SELECTOR, ".select2-container--open .select2-search__field")
        if search:
            try:
                search[-1].send_keys(Keys.ESCAPE)
            except Exception:
                pass
        # Esperar a que no haya dropdown abierto
        wait.until_not(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".select2-container--open .select2-results__options")))
    except Exception:
        pass


def _js_mouse_click(driver: WebDriver, element) -> None:
    try:
        driver.execute_script(
            "var e=arguments[0]; ['mousemove','mousedown','mouseup','click'].forEach(function(t){e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}))});",
            element,
        )
    except Exception:
        try:
            element.click()
        except Exception:
            pass


def _fill_select2(driver: WebDriver, base_el, value: str, wait: WebDriverWait) -> None:
    select_id_initial = base_el.get_attribute("id") or ""

    def _attempt() -> bool:
        select_id = select_id_initial or base_el.get_attribute("id") or ""
        cur_base = driver.find_element(By.ID, select_id) if select_id else base_el

        _close_any_select2(driver, wait)
        rendered_css = f"#select2-{select_id}-container" if select_id else None
        results_css = f"#select2-{select_id}-results" if select_id else None

        container = cur_base.find_element(By.XPATH, "./following-sibling::*[contains(@class,'select2')][1]")
        try:
            selection = container.find_element(By.CSS_SELECTOR, ".select2-selection")
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".select2-selection")))
            selection.click()
        except Exception:
            wait.until(EC.element_to_be_clickable((By.XPATH, "./following-sibling::*[contains(@class,'select2')][1]")))
            container.click()

        query_text = value
        if select_id in {"idCliente", "idProductor"} and "," in value:
            head = value.split(",", 1)[0].strip()
            if head:
                query_text = head

        search_inputs = driver.find_elements(By.CSS_SELECTOR, ".select2-container .select2-search__field")
        if not search_inputs:
            search_inputs = driver.find_elements(By.XPATH, "//input[contains(@class,'select2-search__field')]")
        target_input = None
        if search_inputs:
            target_input = search_inputs[-1]
            try:
                target_input.clear()
            except Exception:
                pass
            target_input.send_keys(query_text)
        else:
            selection.send_keys(query_text)

        # Esperar resultados del contenedor específico si existe
        end = time.time() + 3.0
        while time.time() < end:
            try:
                if results_css and driver.find_elements(By.CSS_SELECTOR, f"{results_css} .select2-results__option"):
                    break
                if driver.find_elements(By.CSS_SELECTOR, ".select2-results__option:not(.select2-results__message)"):
                    break
            except Exception:
                pass
            time.sleep(0.05)

        time.sleep(0.15)

        # ENTER si hay input y opciones reales
        used_enter = False
        if target_input and driver.find_elements(By.CSS_SELECTOR, ".select2-results__option:not(.select2-results__message)"):
            try:
                target_input.send_keys(Keys.ENTER)
                used_enter = True
            except Exception:
                used_enter = False

        if not used_enter:
            # Buscar coincidencia exacta en contenedor específico, luego contains
            def list_opts():
                if results_css:
                    els = driver.find_elements(By.CSS_SELECTOR, f"{results_css} .select2-results__option:not(.select2-results__message)")
                    if els:
                        return els
                return driver.find_elements(By.CSS_SELECTOR, ".select2-results__option:not(.select2-results__message)")

            results = list_opts()
            target_norm_full = _normalize_text(value)
            target_norm_query = _normalize_text(query_text)
            chosen = None
            for li in results:
                try:
                    if _normalize_text(li.text) in {target_norm_full, target_norm_query}:
                        chosen = li
                        break
                except Exception:
                    continue
            if not chosen:
                for li in results:
                    try:
                        if target_norm_full in _normalize_text(li.text) or target_norm_query in _normalize_text(li.text):
                            chosen = li
                            break
                    except Exception:
                        continue
            if not chosen and results:
                # Si no hay coincidencias, intentar la resaltada
                hl = driver.find_elements(By.CSS_SELECTOR, ".select2-results__option--highlighted")
                chosen = hl[0] if hl else results[0]
            if chosen:
                _js_mouse_click(driver, chosen)

        # Confirmar selección
        try:
            wait.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))
        except Exception:
            pass
        if rendered_css:
            targets = {_normalize_text(value), _normalize_text(query_text)}
            end2 = time.time() + 2.0
            while time.time() < end2:
                try:
                    txt = (driver.find_element(By.CSS_SELECTOR, rendered_css).text or "").strip()
                    if _normalize_text(txt) in targets and txt and "Buscar" not in txt and "Seleccione" not in txt:
                        break
                except Exception:
                    pass
                time.sleep(0.05)
        try:
            driver.execute_script("document.activeElement && document.activeElement.blur();")
        except Exception:
            pass
        return True

    for _ in range(3):
        try:
            if _attempt():
                return
        except (StaleElementReferenceException, WebDriverException):
            time.sleep(0.15)
            continue
    raise StaleElementReferenceException("select2 fill failed after retries")


def _fill_autocomplete(driver: WebDriver, el, value: str, wait: WebDriverWait) -> None:
    el.clear()
    el.send_keys(value[:4])
    candidates = [
        (By.CSS_SELECTOR, "[role='listbox'] li, ul.ui-autocomplete li, .select2-results__option"),
        (By.XPATH, "//li[contains(@class,'ui-menu-item') or contains(@class,'select2-results__option')]"),
    ]
    options = None
    for by, sel in candidates:
        try:
            options = wait.until(EC.presence_of_all_elements_located((by, sel)))
            if options:
                break
        except Exception:
            continue
    if options:
        try:
            options[0].click()
        except Exception:
            el.send_keys(Keys.ARROW_DOWN)
            el.send_keys(Keys.ENTER)
    else:
        el.send_keys(Keys.ENTER)
    try:
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true })); arguments[0].blur();", el)
    except Exception:
        pass


class AbsaNetForm:
    def __init__(self, driver: WebDriver, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def build_fill_plan(self, data: PolicyData, mapping: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], Any]]:
        plan: List[Tuple[str, Dict[str, Any], Any]] = []

        fields = mapping.get("fields", {})

        def add(field_key: str, value: Any, tab_key: str | None = None) -> None:
            if value in (None, ""):
                return
            selector = fields.get(field_key)
            if not selector:
                return
            action = {"type": "fill", "selector": selector, "value": value, "tab": tab_key}
            plan.append((field_key, action, value))

        # Condiciones (primer tab) - Riesgo antes que cliente para evitar interferencias
        add("productor", data.productor, tab_key="condiciones")
        add("aseguradora", data.aseguradora, tab_key="condiciones")
        add("riesgo", data.riesgo, tab_key="condiciones")
        add("cliente", data.cliente, tab_key="condiciones")
        add("moneda", data.moneda, tab_key="condiciones")
        add("tipo_contacto_ssn", data.tipo_contacto_ssn, tab_key="condiciones")
        add("tipo_iva", data.tipo_iva, tab_key="condiciones")
        add("tipo_renovacion", data.tipo_renovacion, tab_key="condiciones")
        add("clausula_ajuste", data.clausula_ajuste, tab_key="condiciones")
        add("tipo_vigencia", data.tipo_vigencia, tab_key="condiciones")
        add("inicio_vigencia", data.inicio_vigencia, tab_key="condiciones")
        add("refacturacion", data.refacturacion, tab_key="condiciones")

        # Vehículo
        add("marca", data.marca, tab_key="vehiculo")
        add("anio", data.anio, tab_key="vehiculo")
        add("patente", data.patente, tab_key="vehiculo")
        add("chasis", data.chasis, tab_key="vehiculo")
        add("motor", data.motor, tab_key="vehiculo")

        # Montos / Póliza / Fechas complementarias
        add("prima_total", data.prima_total, tab_key="montos")
        add("premio_total", data.premio_total, tab_key="montos")
        add("numero_poliza", data.numero_poliza, tab_key="montos")
        add("fecha_emision", data.fecha_emision, tab_key="montos")
        add("vencimiento_primera_cuota", data.vencimiento_primera_cuota, tab_key="montos")

        return plan

    def _click_tab(self, mapping: Dict[str, Any], tab_key: str) -> None:
        tab = mapping.get("tabs", {}).get(tab_key)
        if not tab:
            return
        by = _by_from_string(tab["click"]["by"]) if isinstance(tab.get("click"), dict) else By.CSS_SELECTOR
        value = tab["click"]["value"] if isinstance(tab.get("click"), dict) else str(tab.get("click"))
        try:
            el = self.wait.until(EC.element_to_be_clickable((by, value)))
            el.click()
        except Exception:
            return

    def fill_from_plan(self, plan: List[Tuple[str, Dict[str, Any], Any]], mapping: Dict[str, Any], dry_run: bool = True) -> List[str]:
        logs: List[str] = []
        current_tab: str | None = None
        value_map: Dict[str, Dict[str, str]] = mapping.get("select_value_map", {})
        for field_key, action, value in plan:
            # Cerrar cualquier select2 abierto antes de interactuar con el siguiente campo
            _close_any_select2(self.driver, self.wait)
            tab = action.get("tab")
            if tab and tab != current_tab:
                self._click_tab(mapping, tab)
                current_tab = tab
                logs.append(f"Switched to tab: {tab}")
            selector = action["selector"]
            by = _by_from_string(selector.get("by", "css"))
            sel = selector.get("value")
            typ = str(selector.get("type", "input")).lower()
            mapped_value = value
            if typ == "select":
                m = value_map.get(field_key, {})
                if value in m:
                    mapped_value = m[value]
                else:
                    mv = m.get(str(value))
                    if mv is not None:
                        mapped_value = mv
            if dry_run:
                logs.append(f"Would fill {field_key} -> {mapped_value} at {by}={sel} ({typ})")
                continue
            try:
                el = self.wait.until(EC.presence_of_element_located((by, sel)))
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                except Exception:
                    pass
                if typ == "select":
                    if not _js_select_by_text_or_value(self.driver, el, mapped_value):
                        _select_by_visible_text_tolerant(Select(el), mapped_value)
                elif typ == "select2":
                    _fill_select2(self.driver, el, str(mapped_value), self.wait)
                elif typ == "autocomplete":
                    _fill_autocomplete(self.driver, el, str(mapped_value), self.wait)
                else:
                    try:
                        el.clear()
                    except Exception:
                        pass
                    el.send_keys(str(mapped_value))
                logs.append(f"Filled {field_key}")
            except Exception as e:
                logs.append(f"ERROR filling {field_key}: {e}")
                continue
        return logs


def load_mapping(yaml_path: str) -> Dict[str, Any]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
