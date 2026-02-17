from django.conf import settings
from django.core.mail import send_mail

from .models import Invitation


def send_invitation(invitation: Invitation) -> None:
    """Send an invitation through the requested channel.

    SMS integration is left as a provider adapter and currently logs as sent.
    """
    accept_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')}/invite/{invitation.token}"

    if invitation.channel == "email":
        subject = f"Invitation: {invitation.enrollment.campaign.name}"
        message = (
            f"You have been invited to a vetting process.\n\n"
            f"Campaign: {invitation.enrollment.campaign.name}\n"
            f"Candidate: {invitation.enrollment.candidate.first_name} {invitation.enrollment.candidate.last_name}\n"
            f"Accept invitation: {accept_url}\n"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[invitation.send_to],
            fail_silently=False,
        )
        return

    # Placeholder for SMS provider integration.
    # This marks the invitation as sent for now.
    return
