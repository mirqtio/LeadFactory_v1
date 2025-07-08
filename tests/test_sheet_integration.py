"""Tests for Google Sheets integration."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from scripts.sheet_to_yaml import SheetToYamlConverter


class TestSheetToYamlConverter:
    """Test the Google Sheets to YAML converter."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Google service account credentials."""
        return json.dumps({
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            "client_email": "test@test.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        })
    
    @pytest.fixture
    def mock_sheet_data(self):
        """Mock data structure from Google Sheets."""
        return {
            'tiers': {
                'tierA': {'min': 80.0, 'label': 'A'},
                'tierB': {'min': 60.0, 'label': 'B'},
                'tierC': {'min': 40.0, 'label': 'C'},
                'tierD': {'min': 0.0, 'label': 'D'}
            },
            'components': {
                'company_info': {
                    'weight': 0.3,
                    'factors': {
                        'name_quality': {'weight': 0.5},
                        'industry_classification': {'weight': 0.5}
                    }
                },
                'online_presence': {
                    'weight': 0.4,
                    'factors': {
                        'website_quality': {'weight': 0.6},
                        'ssl_certificate': {'weight': 0.4}
                    }
                },
                'business_validation': {
                    'weight': 0.3,
                    'factors': {
                        'license_verified': {'weight': 1.0}
                    }
                }
            },
            'sha': 'abc123'
        }
    
    def test_parse_tiers(self):
        """Test parsing tier data from sheet values."""
        converter = SheetToYamlConverter()
        
        sheet_values = [
            ['tierA', '80', 'A'],
            ['tierB', '60', 'B'],
            ['tierC', '40', 'C'],
            ['tierD', '0', 'D']
        ]
        
        result = converter._parse_tiers(sheet_values)
        
        assert len(result) == 4
        assert result['tierA']['min'] == 80.0
        assert result['tierA']['label'] == 'A'
        assert result['tierD']['min'] == 0.0
        assert result['tierD']['label'] == 'D'
    
    def test_parse_tiers_invalid_data(self):
        """Test parsing tiers handles invalid data gracefully."""
        converter = SheetToYamlConverter()
        
        sheet_values = [
            ['tierA', 'invalid', 'A'],  # Invalid number
            ['tierB', '60', 'B'],
            ['incomplete'],  # Incomplete row
            ['', '', ''],  # Empty row
        ]
        
        result = converter._parse_tiers(sheet_values)
        
        # Should only parse valid tier
        assert len(result) == 1
        assert 'tierB' in result
    
    def test_parse_components(self):
        """Test parsing component data from sheet values."""
        converter = SheetToYamlConverter()
        
        sheet_values = [
            ['Company Info', '0.3', '', ''],  # Component header
            ['  Name Quality', '', '0.5', ''],  # Factor
            ['  Industry Classification', '', '0.5', ''],  # Factor
            ['', '', '', ''],  # Empty row
            ['Online Presence', '0.4', '', ''],  # Component header
            ['  Website Quality', '', '0.6', ''],  # Factor
            ['  SSL Certificate', '', '0.4', ''],  # Factor
        ]
        
        result = converter._parse_components(sheet_values)
        
        assert len(result) == 2
        assert 'company_info' in result
        assert result['company_info']['weight'] == 0.3
        assert len(result['company_info']['factors']) == 2
        assert result['company_info']['factors']['name_quality']['weight'] == 0.5
    
    def test_validate_structure_valid(self, mock_sheet_data):
        """Test validation passes for valid structure."""
        converter = SheetToYamlConverter()
        
        errors = converter.validate_structure(mock_sheet_data)
        
        assert len(errors) == 0
    
    def test_validate_structure_missing_tiers(self):
        """Test validation catches missing tiers."""
        converter = SheetToYamlConverter()
        
        data = {
            'tiers': {
                'tierA': {'min': 80.0, 'label': 'A'},
                'tierB': {'min': 60.0, 'label': 'B'}
                # Missing C and D
            },
            'components': {
                'comp1': {'weight': 1.0, 'factors': {}}
            }
        }
        
        errors = converter.validate_structure(data)
        
        assert len(errors) > 0
        assert any('Missing tier labels' in e for e in errors)
    
    def test_validate_structure_bad_weights(self):
        """Test validation catches bad component weights."""
        converter = SheetToYamlConverter()
        
        data = {
            'tiers': {
                'tierA': {'min': 80.0, 'label': 'A'},
                'tierB': {'min': 60.0, 'label': 'B'},
                'tierC': {'min': 40.0, 'label': 'C'},
                'tierD': {'min': 0.0, 'label': 'D'}
            },
            'components': {
                'comp1': {'weight': 0.6, 'factors': {}},
                'comp2': {'weight': 0.6, 'factors': {}}  # Total = 1.2
            }
        }
        
        errors = converter.validate_structure(data)
        
        assert len(errors) > 0
        assert any('sum to 1.2' in e for e in errors)
    
    def test_validate_structure_bad_factor_weights(self):
        """Test validation catches bad factor weights."""
        converter = SheetToYamlConverter()
        
        data = {
            'tiers': {
                'tierA': {'min': 80.0, 'label': 'A'},
                'tierB': {'min': 60.0, 'label': 'B'},
                'tierC': {'min': 40.0, 'label': 'C'},
                'tierD': {'min': 0.0, 'label': 'D'}
            },
            'components': {
                'comp1': {
                    'weight': 1.0,
                    'factors': {
                        'factor1': {'weight': 0.7},
                        'factor2': {'weight': 0.7}  # Total = 1.4
                    }
                }
            }
        }
        
        errors = converter.validate_structure(data)
        
        assert len(errors) > 0
        assert any('factor weights sum to 1.4' in e for e in errors)
    
    def test_convert_to_yaml(self, mock_sheet_data):
        """Test conversion to YAML format."""
        converter = SheetToYamlConverter()
        
        yaml_content = converter.convert_to_yaml(mock_sheet_data)
        
        # Check key elements are present
        assert '# LeadFactory Scoring Configuration' in yaml_content
        assert 'version: "1.0"' in yaml_content
        assert '# Tier thresholds - used for analytics only in Phase 0' in yaml_content
        assert 'A: {min: 80.0, label: "A"}' in yaml_content
        assert '# Component weights must sum to 1.0' in yaml_content
        assert 'company_info:' in yaml_content
        assert 'weight: 0.3' in yaml_content
        assert 'formulas:' in yaml_content
    
    @patch('scripts.sheet_to_yaml.build')
    @patch('scripts.sheet_to_yaml.service_account')
    def test_fetch_sheet_data(self, mock_service_account, mock_build, mock_credentials):
        """Test fetching data from Google Sheets API."""
        # Mock the Google Sheets service
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock API responses
        mock_values = MagicMock()
        mock_service.spreadsheets().values().get.return_value = mock_values
        
        # Set up different responses for different ranges
        def execute_side_effect(*args, **kwargs):
            # Check which range was requested
            range_param = mock_values.get.call_args[1]['range']
            
            if 'A2:C6' in range_param:  # Tiers
                return {
                    'values': [
                        ['tierA', '80', 'A'],
                        ['tierB', '60', 'B'],
                        ['tierC', '40', 'C'],
                        ['tierD', '0', 'D']
                    ]
                }
            elif 'A10:E50' in range_param:  # Components
                return {
                    'values': [
                        ['Company Info', '0.3', '', ''],
                        ['  Name Quality', '', '0.5', '']
                    ]
                }
            elif 'Z1' in range_param:  # SHA
                return {'values': [['test-sha']]}
            
            return {'values': []}
        
        mock_values.execute.side_effect = execute_side_effect
        
        # Create converter and fetch data
        converter = SheetToYamlConverter(mock_credentials)
        result = converter.fetch_sheet_data('test-sheet-id', 'test-tab')
        
        assert 'tiers' in result
        assert 'components' in result
        assert result['sha'] == 'test-sha'
    
    def test_main_function(self, tmp_path, monkeypatch, mock_credentials):
        """Test the main function end-to-end."""
        # Mock environment and arguments
        monkeypatch.setenv('GOOGLE_SHEETS_CREDENTIALS', mock_credentials)
        
        # Create a mock converter
        with patch('scripts.sheet_to_yaml.SheetToYamlConverter') as MockConverter:
            mock_instance = MockConverter.return_value
            mock_instance.fetch_sheet_data.return_value = {
                'tiers': {
                    'tierA': {'min': 80.0, 'label': 'A'},
                    'tierB': {'min': 60.0, 'label': 'B'},
                    'tierC': {'min': 40.0, 'label': 'C'},
                    'tierD': {'min': 0.0, 'label': 'D'}
                },
                'components': {
                    'comp1': {'weight': 1.0, 'factors': {}}
                },
                'sha': 'test-sha'
            }
            mock_instance.validate_structure.return_value = []
            mock_instance.convert_to_yaml.return_value = "test yaml content"
            
            # Mock command line arguments
            import sys
            output_file = tmp_path / "output.yaml"
            sys.argv = [
                'sheet_to_yaml.py',
                '--sheet-id', 'test-id',
                '--tab', 'test-tab',
                '--output', str(output_file)
            ]
            
            # Run main
            from scripts.sheet_to_yaml import main
            main()
            
            # Check output file was created
            assert output_file.exists()
            assert output_file.read_text() == "test yaml content"