from django.db.models.signals import post_save
from django.dispatch import receiver

from .case_sync import sync_case_interview_outcome
from .models import InterviewResponse, InterviewSession
from .tasks import analyze_response_task


def _response_has_analysis_inputs(response: InterviewResponse) -> bool:
    if (response.transcript or "").strip():
        return True
    if response.video_file or response.video_url or response.audio_file:
        return True
    return False


@receiver(post_save, sender=InterviewResponse)
def queue_response_analysis(sender, instance, created, **kwargs):
    if not created:
        return
    if not _response_has_analysis_inputs(instance):
        return
    analyze_response_task.delay(instance.id)


@receiver(post_save, sender=InterviewSession)
def sync_case_status_on_session_completion(sender, instance, **kwargs):
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "status" not in update_fields:
        return

    if instance.status != "completed" or instance.overall_score is None:
        return

    sync_case_interview_outcome(
        case=instance.case,
        interview_score=instance.overall_score,
    )
