# backend/apps/interviews/ai_engine.py
import openai
from django.conf import settings
import json
from .models import DynamicInterviewSession, InterviewExchange

openai.api_key = settings.OPENAI_API_KEY

class DynamicInterviewEngine:
    """AI engine that generates contextual interview questions"""

    def __init__(self, session):
        self.session = session
        self.conversation_history = session.conversation_history
        self.applicant_context = session.applicant_context

    def generate_next_question(self):
        """Generate the next interview question based on context"""

        # Check if interview should end
        if self.should_end_interview():
            return None

        # Build context for AI
        context = self._build_context()

        # Generate question using GPT-4
        question_data = self._call_gpt4_for_question(context)

        # Update session tracking
        self.session.current_question_number += 1
        self.session.topics_covered.append(question_data['topic'])
        self.session.save()

        return question_data

    def _build_context(self):
        """Build comprehensive context for question generation"""

        context = {
            'application_type': self.session.application.application_type,
            'applicant_info': self.applicant_context,
            'conversation_history': self.conversation_history[-5:],  # Last 5 exchanges
            'topics_covered': self.session.topics_covered,
            'inconsistencies': self.session.inconsistencies_found,
            'clarifications_needed': self.session.clarifications_needed,
            'question_count': self.session.current_question_number
        }

        return context

    def _call_gpt4_for_question(self, context):
        """Use GPT-4 to generate contextual question"""

        system_prompt = f"""You are an expert HR interviewer conducting a vetting interview.

CONTEXT:
- Application Type: {context['application_type']}
- Position/Role: {context['applicant_info'].get('position', 'Not specified')}
- Questions Asked So Far: {context['question_count']}
- Topics Covered: {', '.join(context['topics_covered']) if context['topics_covered'] else 'None'}

APPLICANT BACKGROUND (from documents):
{json.dumps(context['applicant_info'], indent=2)}

CONVERSATION SO FAR:
{self._format_conversation_history(context['conversation_history'])}

INCONSISTENCIES DETECTED:
{json.dumps(context['inconsistencies'], indent=2) if context['inconsistencies'] else 'None'}

AREAS NEEDING CLARIFICATION:
{json.dumps(context['clarifications_needed'], indent=2) if context['clarifications_needed'] else 'None'}

YOUR TASK:
Generate the next interview question that:
1. Builds naturally on previous conversation
2. Addresses any inconsistencies or gaps
3. Verifies information from documents
4. Explores relevant experience/qualifications
5. Probes deeper based on previous answers

RULES:
- Ask ONE clear, specific question
- Make it conversational, not interrogative
- If inconsistencies exist, probe them tactfully
- If all topics covered adequately, prepare to conclude
- Keep questions relevant to the vetting purpose

Return ONLY a JSON object with:
{{
    "question": "Your question here",
    "intent": "Brief intent (e.g., 'verify_experience', 'clarify_gap', 'probe_inconsistency')",
    "topic": "Topic category (e.g., 'work_experience', 'education', 'background')",
    "should_end_interview": false or true,
    "reasoning": "Why you're asking this question"
}}
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the next interview question."}
                ],
                temperature=0.7,
                max_tokens=500
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Error generating question: {e}")
            # Fallback question
            return {
                "question": "Is there anything else you'd like to share about your background?",
                "intent": "open_ended",
                "topic": "general",
                "should_end_interview": False,
                "reasoning": "Fallback question due to error"
            }

    def _format_conversation_history(self, history):
        """Format conversation for context"""
        if not history:
            return "No previous conversation."

        formatted = []
        for exchange in history:
            formatted.append(f"Q: {exchange['question']}")
            formatted.append(f"A: {exchange['answer']}\n")

        return "\n".join(formatted)

    def should_end_interview(self):
        """Determine if interview should end"""

        # Maximum questions limit
        if self.session.current_question_number >= 15:
            return True

        # Minimum questions requirement
        if self.session.current_question_number < 5:
            return False

        # Check if sufficient information gathered
        required_topics = ['background', 'experience', 'education', 'motivation']
        covered_topics = set(self.session.topics_covered)

        if not all(topic in covered_topics for topic in required_topics):
            return False

        # Check for unresolved inconsistencies
        if self.session.inconsistencies_found and self.session.current_question_number < 10:
            return False

        # AI decision based on conversation quality
        if self.session.current_question_number >= 8:
            decision = self._ai_should_end_decision()
            return decision

        return False

    def _ai_should_end_decision(self):
        """Use AI to decide if interview should end"""

        prompt = f"""Based on this interview transcript, should we end the interview?

Questions Asked: {self.session.current_question_number}
Topics Covered: {', '.join(self.session.topics_covered)}
Inconsistencies: {len(self.session.inconsistencies_found)}

Conversation:
{self._format_conversation_history(self.conversation_history)}

Have we gathered sufficient information for a thorough vetting assessment?
Are there critical gaps that need addressing?

Return JSON:
{{
    "should_end": true or false,
    "reason": "Explanation",
    "confidence": 0-100
}}
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert interviewer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            result = json.loads(response.choices[0].message.content)
            return result['should_end'] and result['confidence'] > 70

        except:
            return False

    def analyze_response(self, transcript, question_intent):
        """Analyze applicant's response"""

        prompt = f"""Analyze this interview response:

Question Intent: {question_intent}
Applicant's Answer: {transcript}

Previous Context:
{json.dumps(self.applicant_context, indent=2)}

Analyze for:
1. Key information extracted
2. Inconsistencies with previous statements or documents
3. Areas needing clarification
4. Response quality (clarity, completeness, relevance)
5. Sentiment/confidence level
6. Red flags

Return JSON:
{{
    "key_points": ["point1", "point2"],
    "inconsistencies": [
        {{"issue": "description", "severity": "low/medium/high"}}
    ],
    "clarifications_needed": ["what to clarify"],
    "quality_score": 0-100,
    "relevance_score": 0-100,
    "sentiment": "confident/neutral/nervous/evasive",
    "confidence_level": 0-100,
    "red_flags": ["flag1", "flag2"]
}}
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert HR analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            analysis = json.loads(response.choices[0].message.content)

            # Update session with findings
            if analysis.get('inconsistencies'):
                self.session.inconsistencies_found.extend(analysis['inconsistencies'])

            if analysis.get('clarifications_needed'):
                self.session.clarifications_needed.extend(analysis['clarifications_needed'])

            self.session.save()

            return analysis

        except Exception as e:
            print(f"Error analyzing response: {e}")
            return {
                "key_points": [],
                "inconsistencies": [],
                "quality_score": 50,
                "relevance_score": 50,
                "sentiment": "neutral",
                "confidence_level": 50
            }