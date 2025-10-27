"""
AbsaNet form automation module.

This module provides the main AbsaNetForm class for automating form filling
in the AbsaNet system, with support for multiple tabs and field types.
"""
import time
import yaml
from typing import Any, Dict, List, Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..models import PolicyData
from .selenium_helpers import close_any_select2, by_from_string
from .field_fillers import fill_field, fill_items_modal_fields, wait_for_field_post_effect
from .ui_panels import ReviewPanelManager


DEFAULT_TIMEOUT = 20


class AbsaNetForm:
    """
    Main class for automating AbsaNet form filling.
    
    Handles building fill plans, navigating tabs, filling fields,
    and showing preview panels for data review.
    """
    
    def __init__(self, driver: WebDriver, timeout: int = DEFAULT_TIMEOUT) -> None:
        """
        Initialize the form automation handler.
        
        Args:
            driver: Selenium WebDriver instance
            timeout: Timeout in seconds for element waits
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)
        self.panel_manager = ReviewPanelManager(driver)

    def build_fill_plan(self, data: PolicyData, mapping: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], Any]]:
        """
        Build a plan of fields to fill from PolicyData.
        
        Creates an ordered list of (field_key, action, value) tuples based on
        the provided data and mapping configuration. Fields are organized by
        tabs (condiciones, vehiculo, montos) with special ordering for
        dependent fields (aseguradora before riesgo, cliente at end).
        
        Args:
            data: PolicyData instance with values to fill
            mapping: Mapping configuration from YAML
            
        Returns:
            List of (field_key, action_dict, value) tuples
        """
        plan: List[Tuple[str, Dict[str, Any], Any]] = []
        fields = mapping.get("fields", {})

        def add(field_key: str, value: Any, tab_key: str | None = None) -> None:
            """Add a field to the fill plan if value is present."""
            if value in (None, ""):
                return
            sel = fields.get(field_key)
            if not sel:
                return
            plan.append((field_key, {"type": "fill", "selector": sel, "tab": tab_key}, value))

        # Condiciones tab
        # Order matters: aseguradora first, then riesgo (depends on aseguradora), then rest
        add("aseguradora", data.aseguradora, tab_key="condiciones")
        add("riesgo", data.riesgo, tab_key="condiciones")
        add("productor", data.productor, tab_key="condiciones")
        # cliente: execute at END of condiciones tab (added last)
        add("moneda", data.moneda, tab_key="condiciones")
        add("tipo_contacto_ssn", data.tipo_contacto_ssn, tab_key="condiciones")
        add("tipo_iva", data.tipo_iva, tab_key="condiciones")
        add("tipo_renovacion", data.tipo_renovacion, tab_key="condiciones")
        add("clausula_ajuste", data.clausula_ajuste, tab_key="condiciones")
        add("cant_cuotas", getattr(data, "cant_cuotas", None), tab_key="condiciones")
        add("tipo_vigencia", data.tipo_vigencia, tab_key="condiciones")
        add("inicio_vigencia", data.inicio_vigencia, tab_key="condiciones")
        add("refacturacion", data.refacturacion, tab_key="condiciones")
        add("cliente", data.cliente, tab_key="condiciones")

        # Vehiculo tab
        add("marca", data.marca, tab_key="vehiculo")
        add("anio", data.anio, tab_key="vehiculo")
        add("patente", data.patente, tab_key="vehiculo")
        add("chasis", data.chasis, tab_key="vehiculo")
        add("motor", data.motor, tab_key="vehiculo")

        # Montos / Policy / Complementary dates
        add("prima_total", data.prima_total, tab_key="montos")
        add("premio_total", data.premio_total, tab_key="montos")
        add("numero_poliza", data.numero_poliza, tab_key="montos")
        add("fecha_emision", data.fecha_emision, tab_key="montos")
        add("vencimiento_primera_cuota", data.vencimiento_primera_cuota, tab_key="montos")

        return plan

    def _click_tab(self, mapping: Dict[str, Any], tab_key: str) -> None:
        """
        Click a tab to navigate to it.
        
        Args:
            mapping: Mapping configuration with tabs section
            tab_key: Key identifying the tab (condiciones, vehiculo, montos, etc.)
        """
        tab = mapping.get("tabs", {}).get(tab_key)
        if not tab:
            return
        by = by_from_string(tab["click"]["by"]) if isinstance(tab.get("click"), dict) else By.CSS_SELECTOR
        value = tab["click"]["value"] if isinstance(tab.get("click"), dict) else str(tab.get("click"))
        try:
            el = self.wait.until(EC.element_to_be_clickable((by, value)))
            el.click()
        except Exception:
            return

    def show_preview_condiciones(self, data: PolicyData) -> None:
        """Show preview panel for Condiciones tab. Delegates to panel manager."""
        self.panel_manager.show_preview_condiciones(data)

    def show_preview_item(self, data: PolicyData) -> None:
        """Show preview panel for vehicle item. Delegates to panel manager."""
        self.panel_manager.show_preview_item(data)

    def show_preview_condiciones_dict(self, data: Dict[str, Any]) -> None:
        """Show preview panel for Condiciones from dict. Delegates to panel manager."""
        self.panel_manager.show_preview_condiciones_dict(data)

    def show_preview_item_dict(self, data: Dict[str, Any]) -> None:
        """Show preview panel for vehicle item from dict. Delegates to panel manager."""
        self.panel_manager.show_preview_item_dict(data)

    def install_costos_preview_dict(self, data: Dict[str, Any]) -> None:
        """Install automatic costos preview watcher. Delegates to panel manager."""
        self.panel_manager.install_costos_preview_dict(data)

    def show_preview_costos(self, data: Dict[str, Any]) -> None:
        """Show preview panel for costs. Delegates to panel manager."""
        self.panel_manager.show_preview_costos(data)

    def fill_from_plan(self, plan: List[Tuple[str, Dict[str, Any], Any]], mapping: Dict[str, Any], dry_run: bool = True) -> List[str]:
        """
        Execute the fill plan to populate form fields.
        
        Iterates through the plan, switching tabs as needed and filling each field.
        Closes any open Select2 dropdowns before each field to avoid conflicts.
        
        Args:
            plan: Fill plan from build_fill_plan()
            mapping: Mapping configuration
            dry_run: If True, only log what would be filled without actually filling
            
        Returns:
            List of log messages
        """
        logs: List[str] = []
        current_tab: str | None = None
        value_map: Dict[str, Dict[str, str]] = mapping.get("select_value_map", {})
        
        for field_key, action, value in plan:
            # Close any open select2 before next field
            close_any_select2(self.driver, self.wait)
            
            # Switch tab if needed
            tab = action.get("tab")
            if tab and tab != current_tab:
                self._click_tab(mapping, tab)
                current_tab = tab
                logs.append(f"Switched to tab: {tab}")
            
            selector = action["selector"]
            if dry_run:
                logs.append(f"Would fill {field_key}")
                continue
            
            # Actually fill the field
            try:
                fill_field(self.driver, self.wait, field_key, selector, value, value_map)
                wait_for_field_post_effect(self.driver, field_key)
                logs.append(f"Filled {field_key}")
            except Exception as e:
                logs.append(f"ERROR filling {field_key}: {e}")
        
        return logs

    def fill_items_modal(self, data: PolicyData) -> List[str]:
        """
        Fill the items modal (vehicle data) when user opens it.
        
        Waits indefinitely for the user to open ModalGeneral, then fills
        vehicle fields (patente, chasis, motor). Shows a preview panel
        when the modal opens.
        
        Args:
            data: PolicyData with vehicle information
            
        Returns:
            List of log messages
        """
        logs: List[str] = []
        driver = self.driver
        wait = self.wait
        
        # Wait until user opens the modal (no timeout)
        logs.append("Items: esperando apertura de ModalGeneral…")
        modal = None
        while True:
            try:
                candidate = driver.find_element(By.ID, "ModalGeneral")
                if candidate.is_displayed():
                    modal = candidate
                    break
            except Exception:
                pass
            time.sleep(0.05)
        
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", modal)
        except Exception:
            pass
        
        # Show preview as soon as modal opens
        try:
            self.show_preview_item(data)
        except Exception:
            pass
        
        # Show review panel with key item fields
        try:
            rows: List[Tuple[str, Any]] = [
                ("anio", getattr(data, "anio", None)),
                ("marca", getattr(data, "marca", None)),
                ("patente", getattr(data, "patente", None)),
                ("chasis", getattr(data, "chasis", None)),
                ("motor", getattr(data, "motor", None)),
            ]
            self.panel_manager.show_review_panel('Item Vehículo (revisión)', rows)
        except Exception:
            pass

        # Fill fields using dedicated function
        item_logs = fill_items_modal_fields(
            driver,
            wait,
            anio=getattr(data, "anio", None),
            marca=getattr(data, "marca", None),
            patente=getattr(data, "patente", None),
            chasis=getattr(data, "chasis", None),
            motor=getattr(data, "motor", None)
        )
        logs.extend(item_logs)

        return logs


def load_mapping(yaml_path: str) -> Dict[str, Any]:
    """
    Load field mapping configuration from YAML file.
    
    Args:
        yaml_path: Path to mapping YAML file
        
    Returns:
        Dictionary with mapping configuration
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
