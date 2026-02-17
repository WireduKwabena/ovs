# backend/apps/interviews/enhanced_engine.py
from datetime import timezone
import json

import openai

from apps.interviews.models import InterrogationFlag



class EnhancedInterviewEngine:
    """AI engine with flag-driven interrogation logic"""

    def __init__(self, session):
        self.session = session
        self.pending_flags = session.interrogation_flags.filter(status='pending')
        self.conversation_history = session.conversation_history

    def generate_next_question(self):
        """Generate question targeting unresolved flags"""

        # Priority: Address high/critical severity flags first
        priority_flag = self.pending_flags.filter(
            severity__in=['high', 'critical']
        ).first()

        if priority_flag:
            return self._generate_flag_question(priority_flag)

        # Medium severity flags
        medium_flag = self.pending_flags.filter(severity='medium').first()
        if medium_flag:
            return self._generate_flag_question(medium_flag)

        # All flags resolved - general follow-up
        if not self.pending_flags.exists():
            return self._generate_closing_question()

        return None

    def _generate_flag_question(self, flag):
        """Generate specific question to address a flag"""

        system_prompt = f"""You are a professional vetting investigator conducting a live interrogation.

CRITICAL FLAG TO ADDRESS:
Type: {flag.flag_type}
Severity: {flag.severity}
Context: {flag.context}
Data: {json.dumps(flag.data_point, indent=2)}

CONVERSATION SO FAR:
{self._format_conversation()}

Your task:
1. Generate ONE specific question that directly addresses this inconsistency
2. Be tactful but firm - this is a professional investigation
3. Ask for clarification and specific details
4. Do not accuse, but probe for explanation

Return JSON:
{{
    "question": "Your tactical question here",
    "intent": "resolve_flag_{flag.id}",
    "topic": "{flag.flag_type}",
    "expected_info": ["what you expect to learn"],
    "follow_up_needed": true/false
}}
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate the interrogation question."}
            ],
            temperature=0.5
        )

        question_data = json.loads(response.choices[0].message.content)
        question_data['target_flag_id'] = flag.id

        # Mark flag as "addressed"
        flag.status = 'addressed'
        flag.questions_asked.append(question_data['question'])
        flag.save()

        return question_data

    def analyze_response_for_flag_resolution(self, transcript, flag_id, nonverbal_data):
        """Determine if applicant's response resolves the flag"""

        flag = InterrogationFlag.objects.get(id=flag_id)

        prompt = f"""Analyze if this response resolves the flagged inconsistency.

FLAG:
{flag.context}
Data: {json.dumps(flag.data_point)}

APPLICANT'S RESPONSE:
"{transcript}"

NON-VERBAL INDICATORS:
- Deception Score: {nonverbal_data.get('deception_score', 'N/A')}
- Stress Level: {nonverbal_data.get('stress_level', 'N/A')}
- Eye Contact: {nonverbal_data.get('eye_contact_percentage', 'N/A')}%
- Behavioral Flags: {nonverbal_data.get('behavioral_red_flags', [])}

Evaluate:
1. Does the explanation logically resolve the inconsistency?
2. Is the response consistent with previous statements?
3. Do non-verbal cues suggest deception or stress?
4. Is additional clarification needed?

Return JSON:
{{
    "resolved": true/false,
    "confidence": 0-100,
    "resolution_summary": "Brief summary of explanation",
    "credibility_assessment": "high/medium/low",
    "requires_follow_up": true/false,
    "follow_up_angle": "What to probe next if needed",
    "red_flags": ["any new concerns raised"]
}}
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert interrogator and behavioral analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        assessment = json.loads(response.choices[0].message.content)

        # Update flag
        flag.applicant_explanation = transcript
        flag.resolution_summary = assessment['resolution_summary']
        flag.ai_resolution_confidence = assessment['confidence']

        if assessment['resolved'] and assessment['confidence'] > 70:
            flag.status = 'resolved'
            flag.resolved_at = timezone.now()
        elif not assessment['requires_follow_up']:
            flag.status = 'unresolved'
            flag.requires_human_review = True

        flag.save()

        return assessment
