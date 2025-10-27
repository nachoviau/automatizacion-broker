"""
Tests for field_fillers module.

Tests the field filling strategies and helper functions.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from selenium.webdriver.common.by import By

from automation_broker.fillers.field_fillers import (
    fill_field,
    fill_items_modal_fields,
    wait_for_field_post_effect,
)


class TestWaitForFieldPostEffect:
    """Tests for post-fill waiting logic."""
    
    @patch('automation_broker.fillers.field_fillers.time.sleep')
    def test_waits_after_aseguradora(self, mock_sleep):
        mock_driver = Mock()
        wait_for_field_post_effect(mock_driver, "aseguradora")
        mock_sleep.assert_called_once_with(0.25)
    
    @patch('automation_broker.fillers.field_fillers.time.sleep')
    def test_waits_after_riesgo(self, mock_sleep):
        mock_driver = Mock()
        mock_driver.execute_script.return_value = 1
        wait_for_field_post_effect(mock_driver, "riesgo")
        mock_sleep.assert_called_once_with(0.25)
    
    @patch('automation_broker.fillers.field_fillers.time.sleep')
    def test_no_wait_for_other_fields(self, mock_sleep):
        mock_driver = Mock()
        wait_for_field_post_effect(mock_driver, "cliente")
        mock_sleep.assert_not_called()


class TestFillItemsModalFields:
    """Tests for items modal field filling."""
    
    def test_fills_patente_only(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        logs = fill_items_modal_fields(
            mock_driver,
            mock_wait,
            patente="ABC123"
        )
        
        assert "Items: Filled patente" in logs
        mock_element.send_keys.assert_called()
    
    def test_fills_multiple_fields(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        logs = fill_items_modal_fields(
            mock_driver,
            mock_wait,
            patente="ABC123",
            chasis="CHASIS123",
            motor="MOTOR456"
        )
        
        assert "Items: Filled patente" in logs
        assert "Items: Filled chasis" in logs
        assert "Items: Filled motor" in logs
    
    def test_handles_none_values(self):
        mock_driver = Mock()
        mock_wait = Mock()
        
        logs = fill_items_modal_fields(
            mock_driver,
            mock_wait,
            patente=None,
            chasis=None,
            motor=None
        )
        
        # Should not fill anything
        assert "Items: Filled patente" not in logs
        assert "Items: Filled chasis" not in logs
        assert "Items: Filled motor" not in logs
    
    def test_handles_errors_gracefully(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_wait.until.side_effect = Exception("Element not found")
        
        logs = fill_items_modal_fields(
            mock_driver,
            mock_wait,
            patente="ABC123"
        )
        
        # Should log error
        assert any("ERROR" in log for log in logs)


class TestFillField:
    """Tests for generic field filling function."""
    
    def test_fills_input_field(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        selector = {"by": "id", "value": "testInput", "type": "input"}
        value_map = {}
        
        fill_field(mock_driver, mock_wait, "test_field", selector, "test value", value_map)
        
        mock_element.clear.assert_called()
        mock_element.send_keys.assert_called_with("test value")
    
    def test_handles_inicio_vigencia_specially(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        mock_driver.execute_script.return_value = None
        
        selector = {"by": "id", "value": "InicioVigencia", "type": "input"}
        value_map = {}
        
        fill_field(mock_driver, mock_wait, "inicio_vigencia", selector, "01/01/2025 00:00:00", value_map)
        
        # Should use JavaScript to set value
        assert mock_driver.execute_script.called
        # Should extract date part only
        call_args = mock_driver.execute_script.call_args[0]
        assert "01/01/2025" in str(call_args)
    
    @patch('automation_broker.fillers.field_fillers.fill_select2')
    def test_fills_select2_field(self, mock_fill_select2):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        selector = {"by": "id", "value": "testSelect2", "type": "select2"}
        value_map = {}
        
        fill_field(mock_driver, mock_wait, "test_field", selector, "test value", value_map)
        
        mock_fill_select2.assert_called_once()
    
    @patch('automation_broker.fillers.field_fillers.fill_autocomplete')
    def test_fills_autocomplete_field(self, mock_fill_autocomplete):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        
        selector = {"by": "id", "value": "testAutocomplete", "type": "autocomplete"}
        value_map = {}
        
        fill_field(mock_driver, mock_wait, "test_field", selector, "test value", value_map)
        
        mock_fill_autocomplete.assert_called_once()
    
    def test_uses_value_map_for_select(self):
        mock_driver = Mock()
        mock_wait = Mock()
        mock_element = Mock()
        mock_wait.until.return_value = mock_element
        mock_driver.execute_script.return_value = True
        
        selector = {"by": "id", "value": "testSelect", "type": "select"}
        value_map = {"test_field": {"input_value": "mapped_value"}}
        
        fill_field(mock_driver, mock_wait, "test_field", selector, "input_value", value_map)
        
        # Should use mapped value
        call_args = mock_driver.execute_script.call_args
        assert "mapped_value" in str(call_args)
