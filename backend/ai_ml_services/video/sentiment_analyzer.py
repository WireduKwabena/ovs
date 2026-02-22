"""
Sentiment Analysis Service
===========================

Emotion and confidence detection from interview transcripts.

Academic Note:
--------------
Uses HuggingFace Transformers for sentiment analysis:
- Pre-trained models fine-tuned on emotion datasets
- BERT-based architecture for context understanding
- Can detect: sentiment, emotion, confidence, stress

Models Used:
1. Sentiment: distilbert-base-uncased-finetuned-sst-2-english
2. Emotion: j-hartmann/emotion-english-distilroberta-base
3. Confidence: Custom scoring based on linguistic features

For academic rigor, you can compare multiple models and report
which performs best for interview evaluation.

Reference:
Devlin, J., et al. (2018). "BERT: Pre-training of Deep Bidirectional Transformers"
"""

from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForSequenceClassification
)
import torch
import numpy as np
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Multi-dimensional sentiment analysis for interview responses.
    
    Analyzes:
    1. Overall sentiment (positive/negative/neutral)
    2. Specific emotions (joy, anger, fear, sadness, etc.)
    3. Confidence level
    4. Emotional stability
    """
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize sentiment analyzer.
        
        Args:
            device: Device to run on ('cuda', 'cpu', or None for auto)
        """
        if device is None:
            self.device = 0 if torch.cuda.is_available() else -1
        else:
            self.device = 0 if device == 'cuda' else -1
        
        logger.info(f"Initializing sentiment analyzers on device: {self.device}")
        
        # Sentiment classifier (positive/negative)
        self.sentiment_classifier = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=self.device
        )
        
        # Emotion classifier (6 emotions)
        self.emotion_classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            device=self.device,
            top_k=None  # Return all emotion scores
        )
        
        logger.info("Sentiment analyzers loaded successfully")
    
    def analyze_sentiment(self, text: str) -> Dict:
        """
        Analyze overall sentiment.
        
        Args:
            text: Input text
        
        Returns:
            Sentiment analysis results
        """
        if not text or len(text.strip()) < 3:
            return {
                'sentiment': 'neutral',
                'score': 0.5,
                'confidence': 0.0
            }
        
        try:
            # Run sentiment analysis
            result = self.sentiment_classifier(text[:512])[0]  # Truncate to 512 tokens
            
            return {
                'sentiment': result['label'].lower(),
                'score': result['score'],
                'confidence': result['score']
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                'sentiment': 'neutral',
                'score': 0.5,
                'confidence': 0.0
            }
    
    def analyze_emotions(self, text: str) -> Dict:
        """
        Analyze specific emotions.
        
        Args:
            text: Input text
        
        Returns:
            Emotion distribution
        """
        if not text or len(text.strip()) < 3:
            return {
                'dominant_emotion': 'neutral',
                'emotion_scores': {},
                'confidence': 0.0
            }
        
        try:
            # Run emotion classification
            results = self.emotion_classifier(text[:512])[0]
            
            # Parse results
            emotion_scores = {item['label']: item['score'] for item in results}
            
            # Find dominant emotion
            dominant = max(emotion_scores.items(), key=lambda x: x[1])
            
            return {
                'dominant_emotion': dominant[0],
                'emotion_scores': emotion_scores,
                'confidence': dominant[1]
            }
        
        except Exception as e:
            logger.error(f"Emotion analysis error: {e}")
            return {
                'dominant_emotion': 'neutral',
                'emotion_scores': {},
                'confidence': 0.0
            }
    
    def analyze_confidence(self, text: str) -> Dict:
        """
        Analyze speaker confidence based on linguistic features.
        
        Academic Note:
        --------------
        Confidence indicators:
        - Positive: Definitive statements, active voice, specific details
        - Negative: Hedging words, passive voice, vague language
        
        This is a rule-based heuristic. For research, compare with
        ML-based confidence detection and validate against human ratings.
        """
        # Confidence-boosting patterns
        confident_patterns = [
            r'\bI (will|can|did|have|am)\b',
            r'\b(definitely|certainly|absolutely|clearly)\b',
            r'\b(achieved|accomplished|completed|delivered)\b',
            r'\b\d+\s*(years?|months?|percent|%)\b',  # Specific numbers
        ]
        
        # Confidence-reducing patterns
        uncertain_patterns = [
            r'\b(maybe|perhaps|possibly|probably|might)\b',
            r'\b(I think|I guess|I suppose|kind of|sort of)\b',
            r'\b(not sure|don\'t know|uncertain)\b',
            r'\bum+\b|\buh+\b',  # Filler words
        ]
        
        text_lower = text.lower()
        
        # Count confident indicators
        confident_count = sum(
            len(re.findall(pattern, text_lower))
            for pattern in confident_patterns
        )
        
        # Count uncertain indicators
        uncertain_count = sum(
            len(re.findall(pattern, text_lower))
            for pattern in uncertain_patterns
        )
        
        # Calculate confidence score
        total_indicators = confident_count + uncertain_count
        
        if total_indicators > 0:
            confidence_ratio = confident_count / total_indicators
            confidence_score = confidence_ratio * 100
        else:
            confidence_score = 50  # Neutral
        
        # Categorize
        if confidence_score >= 70:
            confidence_level = 'high'
        elif confidence_score >= 40:
            confidence_level = 'medium'
        else:
            confidence_level = 'low'
        
        return {
            'confidence_score': round(confidence_score, 2),
            'confidence_level': confidence_level,
            'confident_indicators': confident_count,
            'uncertain_indicators': uncertain_count
        }
    
    def analyze_segment_progression(
        self,
        text: str,
        num_segments: int = 4
    ) -> List[Dict]:
        """
        Analyze sentiment progression through response.
        
        Useful for detecting:
        - Increasing confidence over time
        - Emotional shifts
        - Consistency
        """
        if not text or len(text.split()) < num_segments * 5:
            return []
        
        # Split into segments
        words = text.split()
        segment_size = len(words) // num_segments
        
        progressions = []
        
        for i in range(num_segments):
            start = i * segment_size
            end = start + segment_size if i < num_segments - 1 else len(words)
            segment_text = ' '.join(words[start:end])
            
            # Analyze segment
            sentiment = self.analyze_sentiment(segment_text)
            emotions = self.analyze_emotions(segment_text)
            
            progressions.append({
                'segment_number': i + 1,
                'sentiment': sentiment['sentiment'],
                'sentiment_score': sentiment['score'],
                'dominant_emotion': emotions['dominant_emotion'],
                'text_preview': segment_text[:100] + '...'
            })
        
        return progressions
    
    def comprehensive_analysis(self, text: str) -> Dict:
        """
        Complete sentiment analysis combining all methods.
        
        Args:
            text: Interview response transcript
        
        Returns:
            Comprehensive analysis results
        """
        logger.info("Running comprehensive sentiment analysis")
        
        # Overall sentiment
        sentiment = self.analyze_sentiment(text)
        
        # Emotions
        emotions = self.analyze_emotions(text)
        
        # Confidence
        confidence = self.analyze_confidence(text)
        
        # Progression
        progression = self.analyze_segment_progression(text)
        
        # Calculate aggregate sentiment score (0-100)
        # Weighted combination of sentiment and emotions
        sentiment_value = sentiment['score'] if sentiment['sentiment'] == 'positive' else (1 - sentiment['score'])
        
        # Positive emotions boost score
        positive_emotions = ['joy', 'surprise']
        negative_emotions = ['anger', 'fear', 'sadness']
        
        emotion_boost = sum(
            emotions['emotion_scores'].get(e, 0)
            for e in positive_emotions
        )
        
        emotion_penalty = sum(
            emotions['emotion_scores'].get(e, 0)
            for e in negative_emotions
        )
        
        aggregate_score = (
            sentiment_value * 0.5 +
            emotion_boost * 0.3 -
            emotion_penalty * 0.2 +
            (confidence['confidence_score'] / 100) * 0.2
        ) * 100
        
        aggregate_score = max(0, min(100, aggregate_score))
        
        return {
            'sentiment': sentiment,
            'emotions': emotions,
            'confidence': confidence,
            'progression': progression,
            'aggregate_sentiment_score': round(aggregate_score, 2),
            'overall_assessment': self._generate_assessment(
                sentiment, emotions, confidence, aggregate_score
            )
        }
    
    def _generate_assessment(
        self,
        sentiment: Dict,
        emotions: Dict,
        confidence: Dict,
        score: float
    ) -> str:
        """Generate human-readable assessment."""
        assessments = []
        
        # Sentiment
        if sentiment['sentiment'] == 'positive':
            assessments.append("Positive tone")
        elif sentiment['sentiment'] == 'negative':
            assessments.append("Negative tone")
        
        # Emotions
        dominant = emotions['dominant_emotion']
        if dominant in ['joy', 'surprise']:
            assessments.append(f"Shows {dominant}")
        elif dominant in ['anger', 'fear', 'sadness']:
            assessments.append(f"Exhibits {dominant}")
        
        # Confidence
        assessments.append(f"{confidence['confidence_level']} confidence")
        
        # Overall
        if score >= 75:
            assessments.append("Strong delivery")
        elif score >= 50:
            assessments.append("Adequate delivery")
        else:
            assessments.append("Needs improvement")
        
        return ". ".join(assessments) + "."


# Django integration
def analyze_response_sentiment(response_id: int) -> Dict:
    """
    Analyze sentiment for interview response.
    
    Usage in Celery task:
    ```python
    from ai_ml_services.video.sentiment_analyzer import analyze_response_sentiment
    
    result = analyze_response_sentiment(response_id=123)
    ```
    """
    from apps.interviews.models import InterviewResponse
    
    # Get response
    response = InterviewResponse.objects.get(id=response_id)
    
    if not response.transcript:
        raise ValueError(f"Response {response_id} has no transcript")
    
    # Initialize analyzer
    analyzer = SentimentAnalyzer()
    
    # Analyze
    result = analyzer.comprehensive_analysis(response.transcript)
    
    # Update response
    response.sentiment = result['sentiment']['sentiment']
    response.sentiment_score = result['aggregate_sentiment_score']
    response.save()
    
    logger.info(f"Sentiment analysis complete for response {response_id}")
    
    return result


if __name__ == "__main__":
    # Test analyzer
    analyzer = SentimentAnalyzer()
    
    # Test text
    test_text = """
    I am absolutely confident in my abilities. I have five years of experience
    in software development and have successfully delivered multiple projects.
    I'm excited about this opportunity and believe I can make a significant
    contribution to your team.
    """
    
    result = analyzer.comprehensive_analysis(test_text)
    
    print("Sentiment:", result['sentiment'])
    print("Emotions:", result['emotions'])
    print("Confidence:", result['confidence'])
    print("Aggregate Score:", result['aggregate_sentiment_score'])
    print("Assessment:", result['overall_assessment'])
