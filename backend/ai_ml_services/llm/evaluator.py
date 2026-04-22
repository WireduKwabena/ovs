"""
LLM Evaluator
=============

Use GPT-4 or Claude to evaluate interview responses.

Academic Note:
--------------
Large Language Models as evaluators:
- Provide nuanced, context-aware assessment
- Can follow complex rubrics
- More consistent than human raters (when prompted well)
- Cost-effective compared to manual review

Research shows LLM evaluations correlate highly with expert human ratings.
"""

import json
from typing import Dict, List, Optional
import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMEvaluator:
    """Evaluate interview responses using LLMs."""
    
    def __init__(
        self,
        model: str = 'gpt-4',
        api_key: str = None,
        temperature: float = 0.3,
        base_url: str = None,
    ):
        """
        Initialize LLM evaluator.
        
        Args:
            model: 'gpt-4', 'gpt-3.5-turbo', 'claude-3-5-sonnet'
            api_key: API key (or from environment)
            temperature: Randomness (0=deterministic, 1=creative)
            base_url: Custom base URL (used for Ollama: 'http://localhost:11434/v1')
        """
        self.model = model
        self.temperature = temperature
        
        if 'gpt' in model.lower():
            self.client = OpenAI(api_key=api_key)
            self.provider = 'openai'
        elif 'claude' in model.lower():
            try:
                import anthropic
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Anthropic SDK is required for Claude models. Install `anthropic`."
                ) from exc
            self.client = anthropic.Anthropic(api_key=api_key)
            self.provider = 'anthropic'
        elif 'ollama' in model.lower() or base_url is not None:
            _url = base_url or 'http://localhost:11434/v1'
            self.client = OpenAI(base_url=_url, api_key='ollama')
            self.provider = 'openai'  # Ollama is OpenAI-compatible; reuse _call_openai
        else:
            raise ValueError(f"Unknown model: {model}")
    
    def evaluate_response(
        self,
        question: str,
        answer: str,
        rubric: Dict = None,
        context: Dict = None
    ) -> Dict:
        """
        Evaluate interview response.
        
        Args:
            question: Interview question
            answer: Candidate's response
            rubric: Evaluation criteria
            context: Additional context (e.g., flags, job description)
        
        Returns:
            {
                'overall_score': float (0-100),
                'dimension_scores': dict,
                'key_points': list,
                'concerns': list,
                'strengths': list,
                'evaluation': str
            }
        """
        # Default rubric
        if rubric is None:
            rubric = self._get_default_rubric()
        
        # Build prompt
        prompt = self._build_prompt(question, answer, rubric, context)
        
        # Call LLM
        if self.provider == 'openai':
            result = self._call_openai(prompt)
        else:
            result = self._call_anthropic(prompt)
        
        return result
    
    def _build_prompt(
        self,
        question: str,
        answer: str,
        rubric: Dict,
        context: Dict = None
    ) -> str:
        """Build evaluation prompt."""
        
        prompt = f"""You are an expert interviewer evaluating candidate responses.

QUESTION:
{question}

CANDIDATE'S ANSWER:
{answer}

EVALUATION RUBRIC:
{json.dumps(rubric, indent=2)}
"""
        
        if context:
            prompt += f"\n\nADDITIONAL CONTEXT:\n{json.dumps(context, indent=2)}"
        
        prompt += """

Evaluate the response and provide a detailed assessment in JSON format:

{
  "overall_score": <0-100>,
  "dimension_scores": {
    "relevance": <0-100>,
    "completeness": <0-100>,
    "clarity": <0-100>,
    "coherence": <0-100>,
    "professionalism": <0-100>
  },
  "key_points": [
    "<main point 1>",
    "<main point 2>",
    ...
  ],
  "concerns": [
    "<concern 1>",
    "<concern 2>",
    ...
  ],
  "strengths": [
    "<strength 1>",
    "<strength 2>",
    ...
  ],
  "weaknesses": [
    "<weakness 1>",
    "<weakness 2>",
    ...
  ],
  "evaluation": "<detailed written evaluation in 2-3 paragraphs>"
}

Be objective, fair, and specific. Consider:
- Does the answer directly address the question?
- Is it complete and detailed enough?
- Is the communication clear and professional?
- Are there any red flags or inconsistencies?
- What are the standout positives and areas for improvement?
"""
        
        return prompt
    
    def _call_openai(self, prompt: str) -> Dict:
        """Call OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interviewer. Provide evaluations in valid JSON format only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._get_fallback_evaluation()
    
    def _call_anthropic(self, prompt: str) -> Dict:
        """Call Anthropic API."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Parse JSON from response
            content = message.content[0].text
            # Extract JSON from markdown if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            result = json.loads(content.strip())
            return result
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return self._get_fallback_evaluation()
    
    def _get_default_rubric(self) -> Dict:
        """Get default evaluation rubric."""
        return {
            "relevance": {
                "weight": 30,
                "description": "Does the answer directly address the question?"
            },
            "completeness": {
                "weight": 25,
                "description": "Is the answer thorough and detailed?"
            },
            "clarity": {
                "weight": 20,
                "description": "Is the answer clear and well-structured?"
            },
            "coherence": {
                "weight": 15,
                "description": "Is the answer logical and consistent?"
            },
            "professionalism": {
                "weight": 10,
                "description": "Is the tone and language professional?"
            }
        }
    
    def _get_fallback_evaluation(self) -> Dict:
        """Fallback evaluation if API fails."""
        return {
            "overall_score": 50,
            "dimension_scores": {
                "relevance": 50,
                "completeness": 50,
                "clarity": 50,
                "coherence": 50,
                "professionalism": 50
            },
            "key_points": [],
            "concerns": ["API evaluation unavailable - manual review required"],
            "strengths": [],
            "weaknesses": [],
            "evaluation": "Automated evaluation unavailable. Please conduct manual review."
        }


# Django integration
def evaluate_interview_response(response_id: int) -> Dict:
    """
    Evaluate interview response using LLM.
    
    Usage:
    ```python
    from ai_ml_services.llm.evaluator import evaluate_interview_response
    
    result = evaluate_interview_response(response.id)
    ```
    """
    from apps.interviews.models import InterviewResponse
    from django.conf import settings
    
    response = InterviewResponse.objects.get(id=response_id)
    
    # Initialize evaluator
    evaluator = LLMEvaluator(
        model='gpt-4',
        api_key=settings.OPENAI_API_KEY
    )
    
    # Prepare context
    context = {}
    if response.target_flag:
        context['flag'] = {
            'type': response.target_flag.flag_type,
            'description': response.target_flag.description
        }
    
    # Evaluate
    result = evaluator.evaluate_response(
        question=response.question.question_text,
        answer=response.transcript,
        context=context if context else None
    )
    
    # Save to database
    response.response_quality_score = result['overall_score']
    response.relevance_score = result['dimension_scores']['relevance']
    response.completeness_score = result['dimension_scores']['completeness']
    response.coherence_score = result['dimension_scores']['coherence']
    response.llm_evaluation = result
    response.key_points_extracted = result['key_points']
    response.concerns_detected = result['concerns']
    response.save()
    
    logger.info(f"LLM evaluation complete for response {response_id}")
    
    return result


if __name__ == "__main__":
    # Test evaluator
    evaluator = LLMEvaluator('gpt-3.5-turbo')
    
    result = evaluator.evaluate_response(
        question="Tell me about a time you faced a challenging situation at work.",
        answer="I once had a project with a tight deadline. I organized the team, prioritized tasks, and we delivered on time. It taught me the importance of communication and planning."
    )
    
    print(json.dumps(result, indent=2))

