"""
Tests for refactored AbsaNet module.

Tests the main AbsaNetForm class with the new modular structure.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from selenium.webdriver.common.by import By

from automation_broker.fillers.absanet import AbsaNetForm, load_mapping
from automation_broker.models import PolicyData


class TestAbsaNetForm:
    """Tests for AbsaNetForm class."""
    
    def test_initialization(self):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver, timeout=10)
        
        assert form.driver is mock_driver
        assert form.wait is not None
        assert form.panel_manager is not None
    
    def test_build_fill_plan_orders_fields_correctly(self):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        
        data = PolicyData(
            aseguradora="ALLIANZ",
            riesgo="AUTO",
            productor="Test Producer",
            cliente="Test Client",
            moneda="PESOS"
        )
        
        mapping = {
            "fields": {
                "aseguradora": {"by": "id", "value": "idAseguradora", "type": "select"},
                "riesgo": {"by": "id", "value": "idRiesgo", "type": "select2"},
                "productor": {"by": "id", "value": "idProductor", "type": "select2"},
                "cliente": {"by": "id", "value": "idCliente", "type": "select2"},
                "moneda": {"by": "id", "value": "Moneda", "type": "select"},
            }
        }
        
        plan = form.build_fill_plan(data, mapping)
        
        # Check that plan is not empty
        assert len(plan) > 0
        
        # Check that aseguradora comes before riesgo (dependency)
        field_keys = [item[0] for item in plan]
        aseg_idx = field_keys.index("aseguradora")
        riesgo_idx = field_keys.index("riesgo")
        assert aseg_idx < riesgo_idx
        
        # Check that cliente comes last in condiciones tab
        cliente_idx = field_keys.index("cliente")
        moneda_idx = field_keys.index("moneda")
        assert cliente_idx > moneda_idx
    
    def test_build_fill_plan_skips_none_values(self):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        
        data = PolicyData(
            aseguradora="ALLIANZ",
            riesgo=None,  # Should be skipped
            productor="Test Producer"
        )
        
        mapping = {
            "fields": {
                "aseguradora": {"by": "id", "value": "idAseguradora", "type": "select"},
                "riesgo": {"by": "id", "value": "idRiesgo", "type": "select2"},
                "productor": {"by": "id", "value": "idProductor", "type": "select2"},
            }
        }
        
        plan = form.build_fill_plan(data, mapping)
        
        field_keys = [item[0] for item in plan]
        assert "riesgo" not in field_keys
        assert "aseguradora" in field_keys
        assert "productor" in field_keys
    
    def test_build_fill_plan_assigns_tabs(self):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        
        data = PolicyData(
            aseguradora="ALLIANZ",
            patente="ABC123",
            prima_total=1000.0
        )
        
        mapping = {
            "fields": {
                "aseguradora": {"by": "id", "value": "idAseguradora", "type": "select"},
                "patente": {"by": "id", "value": "vehiculoPatente", "type": "input"},
                "prima_total": {"by": "id", "value": "primaTotal", "type": "input"},
            }
        }
        
        plan = form.build_fill_plan(data, mapping)
        
        # Check tabs are assigned correctly
        for field_key, action, value in plan:
            tab = action.get("tab")
            if field_key == "aseguradora":
                assert tab == "condiciones"
            elif field_key == "patente":
                assert tab == "vehiculo"
            elif field_key == "prima_total":
                assert tab == "montos"
    
    @patch('automation_broker.fillers.absanet.close_any_select2')
    @patch('automation_broker.fillers.absanet.fill_field')
    def test_fill_from_plan_dry_run(self, mock_fill_field, mock_close):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        
        plan = [
            ("aseguradora", {"type": "fill", "selector": {}, "tab": "condiciones"}, "ALLIANZ"),
            ("riesgo", {"type": "fill", "selector": {}, "tab": "condiciones"}, "AUTO"),
        ]
        
        mapping = {"select_value_map": {}}
        
        logs = form.fill_from_plan(plan, mapping, dry_run=True)
        
        # Should not actually fill fields
        mock_fill_field.assert_not_called()
        
        # Should log what would be filled
        assert any("Would fill aseguradora" in log for log in logs)
        assert any("Would fill riesgo" in log for log in logs)
    
    @patch('automation_broker.fillers.absanet.close_any_select2')
    @patch('automation_broker.fillers.absanet.fill_field')
    @patch('automation_broker.fillers.absanet.wait_for_field_post_effect')
    def test_fill_from_plan_actually_fills(self, mock_wait_effect, mock_fill_field, mock_close):
        mock_driver = Mock()
        mock_wait = Mock()
        form = AbsaNetForm(mock_driver)
        
        plan = [
            ("aseguradora", {"type": "fill", "selector": {"by": "id", "value": "test"}, "tab": "condiciones"}, "ALLIANZ"),
        ]
        
        mapping = {"select_value_map": {}}
        
        logs = form.fill_from_plan(plan, mapping, dry_run=False)
        
        # Should actually fill field
        mock_fill_field.assert_called_once()
        mock_wait_effect.assert_called_once()
        
        # Should log success
        assert any("Filled aseguradora" in log for log in logs)
    
    @patch('automation_broker.fillers.absanet.close_any_select2')
    @patch('automation_broker.fillers.absanet.fill_field')
    def test_fill_from_plan_handles_errors(self, mock_fill_field, mock_close):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        
        mock_fill_field.side_effect = Exception("Field error")
        
        plan = [
            ("aseguradora", {"type": "fill", "selector": {}, "tab": "condiciones"}, "ALLIANZ"),
        ]
        
        mapping = {"select_value_map": {}}
        
        logs = form.fill_from_plan(plan, mapping, dry_run=False)
        
        # Should log error
        assert any("ERROR filling aseguradora" in log for log in logs)
    
    def test_click_tab(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        form = AbsaNetForm(mock_driver)
        form.wait = mock_wait
        
        mapping = {
            "tabs": {
                "condiciones": {
                    "click": {
                        "by": "css",
                        "value": "#tab-condiciones"
                    }
                }
            }
        }
        
        form._click_tab(mapping, "condiciones")
        
        # Should click the tab element
        mock_element.click.assert_called_once()
    
    def test_preview_methods_delegate_to_panel_manager(self):
        mock_driver = Mock()
        form = AbsaNetForm(mock_driver)
        form.panel_manager = Mock()
        
        data = PolicyData(productor="Test")
        
        # Test all preview methods
        form.show_preview_condiciones(data)
        form.panel_manager.show_preview_condiciones.assert_called_once_with(data)
        
        form.show_preview_item(data)
        form.panel_manager.show_preview_item.assert_called_once_with(data)
        
        data_dict = {"productor": "Test"}
        form.show_preview_condiciones_dict(data_dict)
        form.panel_manager.show_preview_condiciones_dict.assert_called_once_with(data_dict)
        
        form.show_preview_item_dict(data_dict)
        form.panel_manager.show_preview_item_dict.assert_called_once_with(data_dict)
        
        form.install_costos_preview_dict(data_dict)
        form.panel_manager.install_costos_preview_dict.assert_called_once_with(data_dict)
        
        form.show_preview_costos(data_dict)
        form.panel_manager.show_preview_costos.assert_called_once_with(data_dict)


class TestLoadMapping:
    """Tests for load_mapping function."""
    
    @patch('builtins.open', create=True)
    @patch('yaml.safe_load')
    def test_loads_yaml_file(self, mock_yaml_load, mock_open):
        mock_yaml_load.return_value = {"test": "data"}
        
        result = load_mapping("/path/to/mapping.yaml")
        
        assert result == {"test": "data"}
        mock_open.assert_called_once_with("/path/to/mapping.yaml", "r", encoding="utf-8")
        mock_yaml_load.assert_called_once()
