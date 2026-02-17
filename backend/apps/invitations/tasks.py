from celery import shared_task
from django.utils import timezone

from .models import Invitation
from .services import send_invitation


@shared_task(bind=True, max_retries=3)
def send_invitation_task(self, invitation_id):
    invitation = Invitation.objects.select_related("enrollment__campaign", "enrollment__candidate").get(id=invitation_id)

    if invitation.is_expired:
        invitation.status = "expired"
        invitation.save(update_fields=["status", "updated_at"])
        return {"status": "expired", "invitation_id": invitation_id}

    try:
        send_invitation(invitation)
        invitation.status = "sent"
        invitation.sent_at = timezone.now()
        invitation.attempts += 1
        invitation.last_error = ""
        invitation.save(update_fields=["status", "sent_at", "attempts", "last_error", "updated_at"])
        return {"status": "sent", "invitation_id": invitation_id}
    except Exception as exc:
        invitation.status = "failed"
        invitation.attempts += 1
        invitation.last_error = str(exc)
        invitation.save(update_fields=["status", "attempts", "last_error", "updated_at"])
        raise
