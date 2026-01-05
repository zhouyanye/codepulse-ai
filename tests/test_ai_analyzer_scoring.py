import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

import pytest
from unittest.mock import patch, MagicMock
from services.ai_analyzer import AIAnalyzer
from app.core.config import settings

class TestAIAnalyzerScoring:
    @patch('services.ai_analyzer.settings')
    def test_calculate_overall_score_uses_settings(self, mock_settings):
        # Setup mock settings with specific weights
        mock_settings.SCORE_WEIGHT_CODE = 0.5
        mock_settings.SCORE_WEIGHT_COMMUNITY = 0.1
        mock_settings.SCORE_WEIGHT_DOC = 0.1
        mock_settings.SCORE_WEIGHT_MAINTENANCE = 0.1
        mock_settings.SCORE_WEIGHT_SECURITY = 0.2
        
        analyzer = AIAnalyzer()
        
        # Calculate score with all metrics = 100
        # Expected: 100 * (0.5 + 0.1 + 0.1 + 0.1 + 0.2) = 100
        score = analyzer._calculate_overall_score(100, 100, 100, 100, 100)
        assert score == 100.0
        
        # Calculate score with mixed metrics
        # Code=80, Community=60, Doc=90, Maint=70, Sec=50
        # Expected: 80*0.5 + 60*0.1 + 90*0.1 + 70*0.1 + 50*0.2
        # = 40 + 6 + 9 + 7 + 10 = 72
        score = analyzer._calculate_overall_score(80, 60, 90, 70, 50)
        assert score == 72.0

    @patch('services.ai_analyzer.settings')
    def test_calculate_overall_score_default_weights(self, mock_settings):
        # Setup mock settings with default weights
        mock_settings.SCORE_WEIGHT_CODE = 0.3
        mock_settings.SCORE_WEIGHT_COMMUNITY = 0.2
        mock_settings.SCORE_WEIGHT_DOC = 0.15
        mock_settings.SCORE_WEIGHT_MAINTENANCE = 0.15
        mock_settings.SCORE_WEIGHT_SECURITY = 0.2
        
        analyzer = AIAnalyzer()
        
        # Calculate score with mixed metrics
        # Code=80, Community=60, Doc=90, Maint=70, Sec=50
        # Expected: 80*0.3 + 60*0.2 + 90*0.15 + 70*0.15 + 50*0.2
        # = 24 + 12 + 13.5 + 10.5 + 10 = 70.0
        score = analyzer._calculate_overall_score(80, 60, 90, 70, 50)
        assert score == 70.0
