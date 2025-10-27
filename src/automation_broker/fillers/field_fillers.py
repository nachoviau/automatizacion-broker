"""
Field filling strategies for different input types.

This module provides specialized functions for filling different types of
form fields (input, select, select2, autocomplete) with proper handling
for each field type.
"""
import time
from typing import Any, Dict

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .selenium_helpers import (
    js_select_by_text_or_value,
    select_by_visible_text_tolerant,
    fill_select2,
    fill_autocomplete,
)


def fill_field(
    driver: WebDriver,
    wait: WebDriverWait,
    field_key: str,
    selector: Dict[str, Any],
    value: Any,
    value_map: Dict[str, Dict[str, str]]
) -> None:
    """
    Fill a form field based on its type and selector.
    
    Supports multiple field types:
    - input: Regular text input
    - select: HTML select dropdown
    - select2: Select2 enhanced dropdown
    - autocomplete: Autocomplete input field
    
    Includes special handling for specific fields like inicio_vigencia.
    
    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        field_key: Key identifying the field
        selector: Selector dictionary with 'by', 'value', 'type' keys
        value: Value to fill
        value_map: Dictionary mapping field keys to value translations
        
    Raises:
        Exception: If field cannot be located or filled
    """
    by = selector.get("by", "css").lower()
    sel = selector.get("value")
    typ = str(selector.get("type", "input")).lower()
    
    by_map = {"id": By.ID, "css": By.CSS_SELECTOR, "xpath": By.XPATH, "name": By.NAME}
    el = wait.until(EC.presence_of_element_located((by_map.get(by, By.CSS_SELECTOR), sel)))
    
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass

    # Special handling for inicio_vigencia with datepicker/mask
    if field_key == "inicio_vigencia":
        date_text = str(value).strip()
        if " " in date_text:
            date_text = date_text.split(" ", 1)[0]
        try:
            driver.execute_script(
                "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                el,
                date_text,
            )
            try:
                driver.execute_script("arguments[0].blur();", el)
            except Exception:
                pass
            return
        except Exception:
            try:
                el.clear()
            except Exception:
                pass
            try:
                el.send_keys(date_text)
                el.send_keys(Keys.TAB)
            except Exception:
                pass
            return

    # Map values using value_map if available
    mapped_value = value
    if typ == "select":
        m = value_map.get(field_key, {})
        if value in m:
            mapped_value = m[value]
        else:
            mv = m.get(str(value))
            if mv is not None:
                mapped_value = mv
        try:
            js_select_by_text_or_value(driver, el, mapped_value) or select_by_visible_text_tolerant(Select(el), mapped_value)
        except Exception:
            try:
                driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el, str(mapped_value))
            except Exception:
                raise
        return

    if typ == "select2":
        fill_select2(driver, el, str(mapped_value), wait)
        return

    if typ == "autocomplete":
        fill_autocomplete(driver, el, str(mapped_value), wait)
        return

    # Default: regular input
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(str(mapped_value))


def fill_items_modal_fields(
    driver: WebDriver,
    wait: WebDriverWait,
    anio: Any = None,
    marca: Any = None,
    patente: Any = None,
    chasis: Any = None,
    motor: Any = None
) -> list:
    """
    Fill fields in the items modal (vehicle data).
    
    Currently only fills patente, chasis, and motor as text inputs.
    Anio and marca are commented out temporarily.
    
    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        anio: Year (currently not used)
        marca: Brand (currently not used)
        patente: License plate
        chasis: Chassis number
        motor: Motor number
        
    Returns:
        List of log messages
    """
    logs = []
    
    def set_input(input_id: str, text: Any) -> None:
        """Helper to set input field value."""
        try:
            el = wait.until(EC.presence_of_element_located((By.ID, input_id)))
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            except Exception:
                pass
            try:
                el.clear()
            except Exception:
                pass
            el.send_keys(str(text))
        except Exception as e:
            logs.append(f"ERROR: {input_id}: {e}")

    def set_select2(select_id: str, value_text: Any) -> None:
        """Helper to set Select2 field value."""
        try:
            base = wait.until(EC.presence_of_element_located((By.ID, select_id)))
            fill_select2(driver, base, str(value_text), wait, fast=True)
        except Exception as e:
            logs.append(f"ERROR: {select_id}: {e}")

    # anio (temporarily omitted per user request)
    # if anio:
    #     set_select2("Anio", anio)
    #     logs.append("Items: Filled anio")

    # marca (temporarily omitted per user request)
    # marca (select2) - if compound, take first word before ' - '
    # if marca:
    #     mv = str(marca).strip()
    #     if " - " in mv:
    #         mv = mv.split(" - ", 1)[0].strip()
    #     set_select2("Marca", mv)
    #     logs.append("Items: Filled marca")

    # patente, chasis, motor (inputs)
    if patente:
        set_input("Patente", patente)
        logs.append("Items: Filled patente")
    if chasis:
        set_input("Chasis", chasis)
        logs.append("Items: Filled chasis")
    if motor:
        set_input("Motor", motor)
        logs.append("Items: Filled motor")

    return logs


def wait_for_field_post_effect(driver: WebDriver, field_key: str) -> None:
    """
    Wait after filling certain fields that trigger dynamic updates.
    
    Some fields (like aseguradora, riesgo) trigger AJAX calls or dynamic
    updates that need time to complete before proceeding.
    
    Args:
        driver: WebDriver instance
        field_key: Key identifying the field that was just filled
    """
    if field_key == "aseguradora":
        # Allow dependent 'riesgo' to repopulate and stabilize
        time.sleep(0.25)
        # Wait until #idRiesgo looks populated (options > 1 and not a placeholder)
        end = time.time() + 3.0
        while time.time() < end:
            try:
                ready = driver.execute_script(
                    "var s=document.getElementById('idRiesgo');"
                    "if(!s) return false;"
                    "var n=s.options? s.options.length: 0;"
                    "if(n<=1) return false;"
                    "var t=(s.options[0]||{}).text||'';"
                    "t=String(t).toLowerCase();"
                    "return !(t.includes('seleccione')||t.includes('cargando')||t.includes('buscando'));"
                )
                if ready:
                    break
            except Exception:
                pass
            time.sleep(0.1)
    elif field_key == "riesgo":
        # Brief wait for site to process dynamic resets
        try:
            driver.execute_script("return 1")
        except Exception:
            pass
        time.sleep(0.25)
    elif field_key == "cliente":
        # Cliente selection often triggers downstream recalculations
        # Wait for dependent selects to be enabled and (re)populated
        end = time.time() + 3.0
        while time.time() < end:
            try:
                ready = driver.execute_script(
                    "function ok(id){var s=document.getElementById(id); if(!s) return false; if(s.disabled) return false; var n=s.options? s.options.length: 0; if(n<=0) return false; var t=(s.options[0]||{}).text||''; t=String(t).toLowerCase(); return !(t.includes('seleccione')||t.includes('cargando')||t.includes('buscando'));}"
                    "return ok('Moneda') && ok('TipoRenovacion') && ok('TipoVigencia') && ok('NroCuota');"
                )
                if ready:
                    break
            except Exception:
                pass
            time.sleep(0.1)
