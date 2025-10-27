"""
Tests for selenium_helpers module.

Tests the utility functions for Selenium interactions.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from automation_broker.fillers.selenium_helpers import (
    normalize_text,
    by_from_string,
    js_select_by_text_or_value,
    select_by_visible_text_tolerant,
)


class TestNormalizeText:
    """Tests for text normalization function."""
    
    def test_removes_accents(self):
        assert normalize_text("café") == "cafe"
        assert normalize_text("niño") == "nino"
        assert normalize_text("Ángel") == "angel"
    
    def test_converts_to_lowercase(self):
        assert normalize_text("HELLO") == "hello"
        assert normalize_text("MixedCase") == "mixedcase"
    
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"
        assert normalize_text("\thello\n") == "hello"
    
    def test_handles_empty_string(self):
        assert normalize_text("") == ""
    
    def test_handles_combined_transformations(self):
        assert normalize_text("  JOSÉ García  ") == "jose garcia"


class TestByFromString:
    """Tests for locator type conversion."""
    
    def test_converts_id(self):
        assert by_from_string("id") == By.ID
        assert by_from_string("ID") == By.ID
    
    def test_converts_css(self):
        assert by_from_string("css") == By.CSS_SELECTOR
        assert by_from_string("CSS") == By.CSS_SELECTOR
    
    def test_converts_xpath(self):
        assert by_from_string("xpath") == By.XPATH
        assert by_from_string("XPATH") == By.XPATH
    
    def test_converts_name(self):
        assert by_from_string("name") == By.NAME
    
    def test_default_fallback(self):
        assert by_from_string("unknown") == By.CSS_SELECTOR
        assert by_from_string("") == By.CSS_SELECTOR


class TestJsSelectByTextOrValue:
    """Tests for JavaScript-based select option selection."""
    
    def test_returns_false_on_exception(self):
        mock_driver = Mock()
        mock_driver.execute_script.side_effect = Exception("Script error")
        mock_select = Mock()
        
        result = js_select_by_text_or_value(mock_driver, mock_select, "value")
        assert result is False
    
    def test_calls_execute_script(self):
        mock_driver = Mock()
        mock_driver.execute_script.return_value = True
        mock_select = Mock()
        
        result = js_select_by_text_or_value(mock_driver, mock_select, "value")
        assert result is True
        mock_driver.execute_script.assert_called_once()


class TestSelectByVisibleTextTolerant:
    """Tests for tolerant select option selection."""
    
    def test_exact_match_works(self):
        mock_option = Mock()
        mock_option.text = "Test Option"
        mock_option.get_attribute.return_value = "test_value"
        
        mock_select = Mock(spec=Select)
        mock_select.options = [mock_option]
        mock_select.select_by_visible_text.return_value = None
        
        # Should succeed without exception
        select_by_visible_text_tolerant(mock_select, "Test Option")
        mock_select.select_by_visible_text.assert_called_once_with("Test Option")
    
    def test_normalized_match_fallback(self):
        mock_option = Mock()
        mock_option.text = "Opción con Ácento"
        mock_option.get_attribute.return_value = "test_value"
        
        mock_select = Mock(spec=Select)
        mock_select.options = [mock_option]
        mock_select.select_by_visible_text.side_effect = Exception("Not found")
        mock_select.select_by_index.return_value = None
        
        # Should match with normalization
        select_by_visible_text_tolerant(mock_select, "opcion con acento")
        mock_select.select_by_index.assert_called()
    
    def test_partial_match_fallback(self):
        mock_option = Mock()
        mock_option.text = "Very Long Option Text"
        mock_option.get_attribute.return_value = "test_value"
        
        mock_select = Mock(spec=Select)
        mock_select.options = [mock_option]
        mock_select.select_by_visible_text.side_effect = Exception("Not found")
        mock_select.select_by_index.return_value = None
        
        # Should match partial text
        select_by_visible_text_tolerant(mock_select, "long option")
        mock_select.select_by_index.assert_called()
    
    def test_raises_on_no_match(self):
        mock_option = Mock()
        mock_option.text = "Option A"
        mock_option.get_attribute.return_value = "value_a"
        
        mock_select = Mock(spec=Select)
        mock_select.options = [mock_option]
        mock_select.select_by_visible_text.side_effect = Exception("Not found")
        
        with pytest.raises(ValueError, match="No option matched value"):
            select_by_visible_text_tolerant(mock_select, "Option B")
