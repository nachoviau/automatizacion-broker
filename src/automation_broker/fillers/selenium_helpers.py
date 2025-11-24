"""
Selenium helper functions for web form interactions.

This module contains reusable functions for interacting with web elements
using Selenium WebDriver, including specialized handlers for Select2 dropdowns,
autocomplete fields, and various selection strategies.
"""
import time
import unicodedata
from typing import Any

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException


def normalize_text(s: str) -> str:
    """
    Normalize text by removing accents and converting to lowercase.
    
    Args:
        s: Input string to normalize
        
    Returns:
        Normalized string (lowercase, no accents)
    """
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def by_from_string(s: str) -> str:
    """
    Convert string representation of locator type to Selenium By constant.
    
    Args:
        s: String representation ("id", "css", "xpath", "name")
        
    Returns:
        Selenium By constant
    """
    s = s.lower()
    return {
        "id": By.ID,
        "css": By.CSS_SELECTOR,
        "xpath": By.XPATH,
        "name": By.NAME,
    }.get(s, By.CSS_SELECTOR)


def js_select_by_text_or_value(driver: WebDriver, select_el, target: Any) -> bool:
    """
    Select option in standard HTML select using JavaScript by text or value.
    
    Uses exact match first, then partial match with normalization.
    
    Args:
        driver: WebDriver instance
        select_el: Select element
        target: Target value to select
        
    Returns:
        True if selection successful, False otherwise
    """
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


def select_by_visible_text_tolerant(select: Select, value: Any) -> None:
    """
    Select option by visible text with normalization fallback.
    
    Tries exact match first, then normalized match, then partial match.
    
    Args:
        select: Selenium Select object
        value: Value to select
        
    Raises:
        ValueError: If no matching option found
    """
    target_text = str(value)
    try:
        select.select_by_visible_text(target_text)
        return
    except Exception:
        pass
    
    normalized_target = normalize_text(target_text)
    for idx, option in enumerate(select.options):
        if normalize_text(option.text) == normalized_target or normalize_text(option.get_attribute("value")) == normalized_target:
            select.select_by_index(idx)
            return
    
    for idx, option in enumerate(select.options):
        if normalized_target in normalize_text(option.text) or normalized_target in normalize_text(option.get_attribute("value")):
            select.select_by_index(idx)
            return
    
    raise ValueError(f"No option matched value '{target_text}'")


def close_any_select2(driver: WebDriver, wait: WebDriverWait) -> None:
    """
    Close any open Select2 dropdown by sending ESC key.
    
    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
    """
    try:
        search = driver.find_elements(By.CSS_SELECTOR, ".select2-container--open .select2-search__field")
        if search:
            try:
                search[-1].send_keys(Keys.ESCAPE)
            except Exception:
                pass
        # Wait for dropdown to close
        wait.until_not(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".select2-container--open .select2-results__options")))
    except Exception:
        pass


def js_mouse_click(driver: WebDriver, element) -> None:
    """
    Click element using JavaScript mouse events simulation.
    
    Simulates full click sequence: mousemove, mousedown, mouseup, click.
    Falls back to regular click if JavaScript fails.
    
    Args:
        driver: WebDriver instance
        element: Element to click
    """
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


def fill_select2(driver: WebDriver, base_el, value: str, wait: WebDriverWait, fast: bool = False) -> None:
    """
    Fill a Select2 dropdown by searching and clicking the matching option.
    
    Handles special cases for different field types (idRiesgo, idCliente, idProductor).
    Includes retry logic for stale elements.
    
    Args:
        driver: WebDriver instance
        base_el: Base select element (hidden)
        value: Value to search and select
        wait: WebDriverWait instance
        fast: If True, use shorter timeouts
        
    Raises:
        StaleElementReferenceException: If element becomes stale after retries
    """
    select_id_initial = base_el.get_attribute("id") or ""

    def _attempt() -> bool:
        select_id = select_id_initial or base_el.get_attribute("id") or ""
        cur_base = driver.find_element(By.ID, select_id) if select_id else base_el

        # Guard: if riesgo depends on aseguradora, ensure it's ready before opening
        if select_id == "idRiesgo":
            end_ready = time.time() + 4.0
            while time.time() < end_ready:
                try:
                    ready = driver.execute_script(
                        "var a=document.getElementById('idAseguradora');"
                        "var r=document.getElementById('idRiesgo');"
                        "if(!a||!r) return false;"
                        "var av=String(a.value||'');"
                        "var dis=r.disabled===true;"
                        "return av.length>0 && !dis;"
                    )
                    if ready:
                        break
                except Exception:
                    pass
                time.sleep(0.1)

        close_any_select2(driver, wait)
        rendered_css = f"#select2-{select_id}-container" if select_id else None
        results_css = f"#select2-{select_id}-results" if select_id else None

        # Open select2
        container = cur_base.find_element(By.XPATH, "./following-sibling::*[contains(@class,'select2')][1]")
        selection = container.find_element(By.CSS_SELECTOR, ".select2-selection")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".select2-selection")))
        js_mouse_click(driver, selection)
        # Wait for dropdown to open
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))

        # Search input
        search_inputs = driver.find_elements(By.CSS_SELECTOR, ".select2-container .select2-search__field")
        if not search_inputs:
            search_inputs = driver.find_elements(By.XPATH, "//input[contains(@class,'select2-search__field')]")
        si = search_inputs[-1] if search_inputs else None
        if si is not None:
            try:
                driver.execute_script("arguments[0].focus();", si)
            except Exception:
                pass

        # Prepare query text (special handling for productor field)
        query_text = value
        if select_id in {"idProductor"} and "," in value:
            head = value.split(",", 1)[0].strip()
            if head:
                query_text = head

        if si is not None:
            try:
                si.clear()
            except Exception:
                pass
            # Special case: idCliente requires setting value directly via JavaScript for reliability
            if select_id == "idCliente":
                try:
                    # Set value directly via JavaScript to avoid character loss
                    driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        si,
                        query_text
                    )
                    time.sleep(0.2)  # Short wait to start AJAX
                except Exception:
                    si.send_keys(query_text)
                # Extra pause per request to allow remote results to load
                time.sleep(2.0)
            # idRiesgo requires slow typing to trigger AJAX
            elif select_id == "idRiesgo":
                try:
                    # Extra pause before starting to type per request
                    time.sleep(0.5)
                    for ch in str(query_text):
                        si.send_keys(ch)
                        try:
                            driver.execute_script(
                                "arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,key:arguments[1]}));",
                                si,
                                ch,
                            )
                        except Exception:
                            pass
                        time.sleep(0.08)
                except Exception:
                    si.send_keys(query_text)
            else:
                si.send_keys(query_text)
        else:
            js_mouse_click(driver, selection)

        # Wait for results (longer timeout for cliente field with remote search)
        end = time.time() + (0.8 if fast else (5.0 if select_id == "idCliente" else 3.0))
        while time.time() < end:
            try:
                if results_css and driver.find_elements(By.CSS_SELECTOR, f"{results_css} .select2-results__option:not(.select2-results__message)"):
                    break
                if driver.find_elements(By.CSS_SELECTOR, ".select2-results__option:not(.select2-results__message)"):
                    break
            except Exception:
                pass
            time.sleep(0.05)
        time.sleep(0.05 if fast else 0.15)

        def list_opts():
            if results_css:
                els = driver.find_elements(By.CSS_SELECTOR, f"{results_css} .select2-results__option:not(.select2-results__message)")
                if els:
                    return els
            return driver.find_elements(By.CSS_SELECTOR, ".select2-results__option:not(.select2-results__message)")

        results = list_opts()
        
        # Filter out placeholder messages like "Searching...", "No results"
        def is_real_option(li_el) -> bool:
            try:
                t = normalize_text(li_el.text)
            except Exception:
                return False
            if not t:
                return False
            if "buscando" in t:
                return False
            if "sin resultados" in t:
                return False
            if "seleccione" in t:
                return False
            return True
        
        results = [li for li in results if is_real_option(li)]
        target_norm_full = normalize_text(value)
        target_norm_query = normalize_text(query_text)
        
        # Try exact match first
        chosen = None
        for li in results:
            try:
                if normalize_text(li.text) in {target_norm_full, target_norm_query}:
                    chosen = li
                    break
            except Exception:
                continue
        
        # Try partial match
        if not chosen:
            for li in results:
                try:
                    if target_norm_full in normalize_text(li.text) or target_norm_query in normalize_text(li.text):
                        chosen = li
                        break
                except Exception:
                    continue
        
        # Fallback to highlighted or first option
        if not chosen and results:
            hl = driver.find_elements(By.CSS_SELECTOR, ".select2-results__option--highlighted")
            hl = [h for h in hl if is_real_option(h)]
            chosen = hl[0] if hl else results[0]
        
        # Click the chosen option
        if chosen:
            if select_id == "idCliente":
                # Special handling for idCliente (remote AJAX search)
                # Strategy: Try multiple approaches in order until one works
                time.sleep(0.2)  # Give AJAX more time to stabilize
                
                # Approach 1: ENTER key (most reliable for remote search)
                if si is not None:
                    try:
                        # Ensure search input has focus
                        driver.execute_script("arguments[0].focus();", si)
                        time.sleep(0.05)
                        si.send_keys(Keys.ENTER)
                        time.sleep(0.15)
                    except Exception:
                        pass
                
                # Verify if selection was applied
                applied = False
                try:
                    rendered = driver.find_element(By.CSS_SELECTOR, "#select2-idCliente-container").text.strip()
                    applied = (rendered and "Buscar" not in rendered and "Seleccione" not in rendered and rendered != "")
                except Exception:
                    applied = False
                
                # Approach 2: Direct click on highlighted option if ENTER failed
                if not applied:
                    try:
                        time.sleep(0.1)
                        js_mouse_click(driver, chosen)
                        time.sleep(0.15)
                    except Exception:
                        pass
                    
                    # Verify again
                    try:
                        rendered = driver.find_element(By.CSS_SELECTOR, "#select2-idCliente-container").text.strip()
                        applied = (rendered and "Buscar" not in rendered and "Seleccione" not in rendered and rendered != "")
                    except Exception:
                        applied = False
                
                # Approach 3: Force selection via JavaScript as last resort
                if not applied and si is not None:
                    try:
                        # Get the data-select2-id from chosen element
                        val_ds2 = chosen.get_attribute("data-select2-id") or chosen.get_attribute("id") or ""
                        txt_ds2 = chosen.text.strip()
                        if val_ds2 and txt_ds2:
                            # Use jQuery to force selection
                            driver.execute_script("""
                                var id = 'idCliente';
                                var val = arguments[0];
                                var txt = arguments[1];
                                try {
                                    if (window.jQuery && jQuery('#' + id).length) {
                                        jQuery('#' + id).empty().append(new Option(txt, val, true, true));
                                        jQuery('#' + id).trigger({
                                            type: 'select2:select',
                                            params: { data: { id: val, text: txt } }
                                        });
                                        jQuery('#' + id).trigger('change');
                                    }
                                } catch(e) { console.error('Select2 force selection error:', e); }
                            """, val_ds2, txt_ds2)
                            time.sleep(0.1)
                    except Exception as e:
                        pass
            else:
                js_mouse_click(driver, chosen)

        # Wait for dropdown to close
        try:
            wait.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))
        except Exception:
            pass
        
        # Verify selection was rendered
        if rendered_css:
            targets = {normalize_text(value), normalize_text(query_text)}
            end2 = time.time() + (0.6 if fast else 2.0)
            while time.time() < end2:
                try:
                    txt = (driver.find_element(By.CSS_SELECTOR, rendered_css).text or "").strip()
                    if normalize_text(txt) in targets and txt and "Buscar" not in txt and "Seleccione" not in txt:
                        break
                except Exception:
                    pass
                time.sleep(0.05)
        # For riesgo, ensure the selection applied; otherwise signal retry
        if select_id == "idRiesgo":
            try:
                rend = (driver.find_element(By.CSS_SELECTOR, "#select2-idRiesgo-container").text or "").strip()
                ok_txt = normalize_text(rend) in {normalize_text(value), normalize_text(query_text)} and rend and "Seleccione" not in rend and "Buscar" not in rend
            except Exception:
                ok_txt = False
            try:
                hid_val = (driver.find_element(By.ID, "idRiesgo").get_attribute("value") or "").strip()
                ok_val = len(hid_val) > 0
            except Exception:
                ok_val = False
            if not (ok_txt or ok_val):
                return False
        
        # Additional validation for cliente field: ensure selection took effect
        if select_id == "idCliente":
            max_retries = 3
            for retry in range(max_retries):
                try:
                    hid = driver.find_element(By.ID, "idCliente").get_attribute("value") or ""
                    rend = (driver.find_element(By.CSS_SELECTOR, "#select2-idCliente-container").text or "").strip()
                    
                    # Check if selection is valid
                    if hid and hid != "0" and rend and "Buscar" not in rend and "Seleccione" not in rend:
                        break  # Selection successful
                    
                    # Selection failed, try to recover
                    if retry < max_retries - 1:
                        time.sleep(0.2)
                        # Try to click the chosen option again
                        try:
                            if chosen:
                                js_mouse_click(driver, chosen)
                                time.sleep(0.2)
                        except Exception:
                            pass
                except Exception:
                    if retry < max_retries - 1:
                        time.sleep(0.2)
        
        # Blur active element
        try:
            driver.execute_script("document.activeElement && document.activeElement.blur();")
        except Exception:
            pass
        return True

    # Retry logic for stale elements
    for _ in range(3):
        try:
            if _attempt():
                return
        except (StaleElementReferenceException, WebDriverException):
            time.sleep(0.15)
            continue
    raise StaleElementReferenceException("select2 fill failed after retries")


def set_hidden_select_value(driver: WebDriver, select_id: str, value: str, text: str) -> bool:
    """
    Set value of hidden select element directly via JavaScript.
    
    Creates option if it doesn't exist and dispatches change event.
    
    Args:
        driver: WebDriver instance
        select_id: ID of select element
        value: Value to set
        text: Text for the option
        
    Returns:
        True if successful, False otherwise
    """
    js = r"""
    const sel = document.getElementById(arguments[0]);
    if(!sel) return false;
    const val = String(arguments[1]);
    const txt = String(arguments[2]);
    let opt = Array.from(sel.options).find(o => String(o.value)===val);
    if(!opt){ opt = new Option(txt, val, true, true); sel.appendChild(opt); }
    sel.value = val;
    try { sel.dispatchEvent(new Event('change', { bubbles: true })); } catch(e) {}
    return true;
    """
    try:
        return bool(driver.execute_script(js, select_id, value, text))
    except Exception:
        return False


def force_select2_from_highlight(driver: WebDriver, wait: WebDriverWait, select_id: str, fallback_text: str) -> bool:
    """
    Force selection of highlighted or first Select2 option.
    
    Useful for fallback scenarios. Tries jQuery API first, then direct manipulation.
    
    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        select_id: ID of select element
        fallback_text: Fallback text if option text not available
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = driver.find_element(By.XPATH, f"//*[@id='{select_id}']/following-sibling::*[contains(@class,'select2')][1]")
        selection = container.find_element(By.CSS_SELECTOR, ".select2-selection")
        js_mouse_click(driver, selection)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))
        time.sleep(0.1)
        
        # Get highlighted or first option
        hl = driver.find_elements(By.CSS_SELECTOR, f"#select2-{select_id}-results .select2-results__option--highlighted")
        cand = hl[-1] if hl else None
        if not cand:
            opts = driver.find_elements(By.CSS_SELECTOR, f"#select2-{select_id}-results .select2-results__option:not(.select2-results__message)")
            cand = opts[0] if opts else None
        if not cand:
            return False
        
        val_ds2 = cand.get_attribute("data-select2-id") or ""
        txt_ds2 = (cand.text or fallback_text).strip()
        if not val_ds2:
            return False
        
        # Attempt 1: jQuery/select2 API if available (more reliable)
        try:
            used_jq = driver.execute_script(
                "if (window.jQuery) { var id=arguments[0], val=arguments[1], txt=arguments[2]; try { jQuery('#'+id).empty().append(new Option(txt,val,true,true)).trigger({ type:'select2:select', params:{ data:{ id:val, text:txt } } }).trigger('change').select2('close'); return true; } catch(e){ return false; } } return false;",
                select_id,
                val_ds2,
                txt_ds2,
            )
        except Exception:
            used_jq = False
        
        if used_jq:
            try:
                wait.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))
            except Exception:
                pass
            return True
        
        # Attempt 2: direct hidden select setter + explicit close
        ok = set_hidden_select_value(driver, select_id, val_ds2, txt_ds2)
        # Close dropdown explicitly
        try:
            js_mouse_click(driver, selection)
        except Exception:
            pass
        try:
            driver.execute_script("if (window.jQuery) { try { jQuery('#'+arguments[0]).trigger('select2:close'); } catch(e) {} }", select_id)
        except Exception:
            pass
        try:
            wait.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, ".select2-container--open")))
        except Exception:
            pass
        return ok
    except Exception:
        return False


def fill_autocomplete(driver: WebDriver, el, value: str, wait: WebDriverWait) -> None:
    """
    Fill autocomplete field by typing and selecting from dropdown.
    
    Args:
        driver: WebDriver instance
        el: Input element
        value: Value to type
        wait: WebDriverWait instance
    """
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
