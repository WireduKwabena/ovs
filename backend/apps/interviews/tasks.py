from statistics import mean
from pathlib import Path

from celery import shared_task
from django.utils import timezone

from .case_sync import sync_case_interview_outcome
from .models import InterviewResponse, InterviewSession, VideoAnalysis


IDENTITY_DOCUMENT_TYPE_PRIORITY = ("id_card", "passport", "drivers_license")


def _resolve_file_path(file_field) -> str | None:
    if not file_field:
        return None
    try:
        path = file_field.path
    except (AttributeError, OSError, NotImplementedError, TypeError, ValueError):
        return None
    if not path:
        return None
    return path if Path(path).exists() else None


def _select_identity_document_path(case) -> tuple[str | None, str | None]:
    seen_ids = set()
    candidates = list(
        case.documents.filter(document_type__in=IDENTITY_DOCUMENT_TYPE_PRIORITY).order_by(
            "uploaded_at",
            "id",
        )
    ) + list(case.documents.exclude(document_type__in=IDENTITY_DOCUMENT_TYPE_PRIORITY).order_by("uploaded_at", "id"))

    for document in candidates:
        if document.id in seen_ids:
            continue
        seen_ids.add(document.id)
        path = _resolve_file_path(document.file)
        if path:
            return path, document.document_type
    return None, None


def _run_identity_match(response: InterviewResponse) -> dict:
    video_path = _resolve_file_path(response.video_file)
    if not video_path:
        return {
            "enabled": False,
            "success": False,
            "is_match": False,
            "reason": "No local interview video file available for identity matching.",
        }

    case = response.session.case
    document_path, document_type = _select_identity_document_path(case)
    if not document_path:
        return {
            "enabled": False,
            "success": False,
            "is_match": False,
            "reason": "No local identity document (id_card/passport/drivers_license) found.",
        }

    try:
        from ai_ml_services.video.identity_matcher import IdentityMatcher

        matcher = IdentityMatcher()
        result = matcher.match_document_to_interview(
            document_path=document_path,
            interview_video_path=video_path,
        )
    except Exception as exc:
        return {
            "enabled": True,
            "success": False,
            "is_match": False,
            "error": str(exc),
            "document_type": document_type,
        }

    result["document_type"] = document_type
    return result


def _simple_sentiment(transcript: str) -> tuple[str, float]:
    text = (transcript or "").lower()
    positive_tokens = {"yes", "confident", "success", "achieved", "led", "improved"}
    negative_tokens = {"no", "not", "failed", "problem", "struggled", "unclear"}

    positive_hits = sum(token in text for token in positive_tokens)
    negative_hits = sum(token in text for token in negative_tokens)
    score = 50 + ((positive_hits - negative_hits) * 8)
    bounded = max(0, min(100, score))

    if bounded >= 60:
        return "positive", float(bounded)
    if bounded <= 40:
        return "negative", float(bounded)
    return "neutral", float(bounded)


@shared_task(bind=True, max_retries=1)
def analyze_response_task(self, response_id: int):
    try:
        response = InterviewResponse.objects.select_related(
            "question",
            "session",
            "session__case",
        ).get(id=response_id)
    except InterviewResponse.DoesNotExist:
        return {"success": False, "error": f"InterviewResponse {response_id} not found"}

    transcript = (response.transcript or "").strip()
    if not transcript:
        transcript = "No transcript provided."
        response.transcript = transcript

    words = [w for w in transcript.split() if w]
    word_count = len(words)
    unique_terms = []
    for word in words:
        normalized = word.strip(".,!?").lower()
        if len(normalized) > 3 and normalized not in unique_terms:
            unique_terms.append(normalized)

    sentiment, sentiment_score = _simple_sentiment(transcript)
    relevance_score = min(100.0, max(20.0, word_count * 3.0))
    completeness_score = min(100.0, max(10.0, word_count * 2.5))
    coherence_score = min(100.0, max(25.0, 55.0 + (len(unique_terms) * 2.0)))
    response_quality_score = round((relevance_score + completeness_score + coherence_score + sentiment_score) / 4.0, 2)

    concerns = []
    if word_count < 8:
        concerns.append("Response is very short and may require follow-up.")
    if sentiment == "negative":
        concerns.append("Tone indicates potential uncertainty or stress.")

    identity_match = _run_identity_match(response)
    if identity_match.get("enabled") and identity_match.get("success") and not identity_match.get("is_match"):
        concerns.append("Identity mismatch detected between document face and interview face.")

    llm_evaluation = {
        "pipeline": "baseline-heuristic",
        "word_count": word_count,
        "response_quality_score": response_quality_score,
    }

    now = timezone.now()
    if not response.answered_at:
        response.answered_at = now
    response.sentiment = sentiment
    response.sentiment_score = sentiment_score
    response.response_quality_score = response_quality_score
    response.relevance_score = relevance_score
    response.completeness_score = completeness_score
    response.coherence_score = coherence_score
    response.key_points_extracted = unique_terms[:6]
    response.concerns_detected = concerns
    response.llm_evaluation = llm_evaluation
    response.processed_at = now
    response.save(
        update_fields=[
            "transcript",
            "answered_at",
            "sentiment",
            "sentiment_score",
            "response_quality_score",
            "relevance_score",
            "completeness_score",
            "coherence_score",
            "key_points_extracted",
            "concerns_detected",
            "llm_evaluation",
            "processed_at",
        ]
    )

    VideoAnalysis.objects.update_or_create(
        response=response,
        defaults={
            "face_detected": True,
            "face_detection_confidence": 80.0,
            "eye_contact_percentage": min(95.0, max(35.0, response_quality_score - 10.0)),
            "gaze_direction_changes": max(0, int((100 - response_quality_score) / 10)),
            "dominant_emotion": sentiment,
            "emotion_distribution": {sentiment: 1.0},
            "confidence_level": min(100.0, max(20.0, response_quality_score)),
            "stress_level": max(0.0, 100.0 - response_quality_score),
            "head_movement_count": max(0, int((100 - response_quality_score) / 8)),
            "fidgeting_detected": response_quality_score < 45,
            "behavioral_indicators": concerns,
            "raw_analysis_data": {
                "source": "baseline-heuristic",
                "identity_match": identity_match,
            },
            "frames_analyzed": 0,
            "analysis_duration_seconds": 0.0,
        },
    )

    generate_session_summary_task.delay(response.session_id)
    return {"success": True, "response_id": response.id, "quality_score": response_quality_score}


@shared_task(bind=True, max_retries=1)
def generate_session_summary_task(self, session_id: int):
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    responses = list(session.responses.select_related("video_analysis").all().order_by("sequence_number"))
    if not responses:
        return {"success": True, "session_id": session_id, "message": "No responses yet"}

    quality_scores = [r.response_quality_score for r in responses if r.response_quality_score is not None]
    completeness_scores = [r.completeness_score for r in responses if r.completeness_score is not None]
    coherence_scores = [r.coherence_score for r in responses if r.coherence_score is not None]
    confidence_scores = [
        r.video_analysis.confidence_level
        for r in responses
        if hasattr(r, "video_analysis") and r.video_analysis and r.video_analysis.confidence_level is not None
    ]

    session.total_questions_asked = len(responses)
    session.current_question_number = len(responses)
    session.overall_score = round(mean(quality_scores), 2) if quality_scores else None
    session.communication_score = round(mean(completeness_scores), 2) if completeness_scores else None
    session.consistency_score = round(mean(coherence_scores), 2) if coherence_scores else None
    session.confidence_score = round(mean(confidence_scores), 2) if confidence_scores else session.overall_score

    session.key_findings = [f"Processed {len(responses)} responses."]
    unresolved_flags = session.case.interrogation_flags.exclude(status__in=["resolved", "dismissed"]).count()
    session.flags_unresolved_count = unresolved_flags
    session.flags_resolved_count = session.case.interrogation_flags.filter(status="resolved").count()
    session.red_flags_detected = [c for response in responses for c in (response.concerns_detected or [])]
    session.interview_summary = (
        f"Session analyzed with {len(responses)} responses. "
        f"Overall score: {session.overall_score if session.overall_score is not None else 'n/a'}."
    )

    session.save(
        update_fields=[
            "total_questions_asked",
            "current_question_number",
            "overall_score",
            "communication_score",
            "consistency_score",
            "confidence_score",
            "key_findings",
            "flags_unresolved_count",
            "flags_resolved_count",
            "red_flags_detected",
            "interview_summary",
        ]
    )

    if session.status == "completed" and session.overall_score is not None:
        sync_case_interview_outcome(
            case=session.case,
            interview_score=session.overall_score,
        )

    return {"success": True, "session_id": session.id, "responses": len(responses)}
