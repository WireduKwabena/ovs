from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Committee, CommitteeMembership, Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization_type", "is_active", "updated_at")
    list_filter = ("organization_type", "is_active")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "membership_role", "is_active", "is_default", "updated_at")
    list_filter = ("is_active", "is_default", "membership_role")
    search_fields = ("user__email", "organization__name", "title")
    autocomplete_fields = ("user", "organization")
    ordering = ("organization__name", "user__email")


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "committee_type", "is_active", "updated_at")
    list_filter = ("committee_type", "is_active", "organization")
    search_fields = ("name", "code", "organization__name")
    autocomplete_fields = ("organization", "created_by")
    ordering = ("organization__name", "name")


@admin.register(CommitteeMembership)
class CommitteeMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "committee", "committee_role", "can_vote", "is_active", "updated_at")
    list_filter = ("committee_role", "can_vote", "is_active")
    search_fields = ("user__email", "committee__name", "committee__organization__name")
    autocomplete_fields = ("committee", "user", "organization_membership")
    ordering = ("committee__name", "user__email")
    actions = ("promote_selected_to_chair",)

    @admin.action(description="Promote selected memberships to chair (safe reassignment)")
    def promote_selected_to_chair(self, request, queryset):
        promoted_count = 0
        failures: list[str] = []

        memberships = queryset.select_related(
            "committee",
            "user",
            "organization_membership",
        )
        for membership in memberships:
            try:
                CommitteeMembership.assign_active_chair(
                    committee=membership.committee,
                    user=membership.user,
                    organization_membership=membership.organization_membership,
                    can_vote=membership.can_vote,
                )
                promoted_count += 1
            except ValidationError as exc:
                failures.append(
                    f"{membership.user} @ {membership.committee}: {exc}"
                )

        if promoted_count:
            self.message_user(
                request,
                f"Promoted {promoted_count} membership(s) to committee chair.",
                level=messages.SUCCESS,
            )
        if failures:
            preview = "; ".join(failures[:3])
            if len(failures) > 3:
                preview += f"; ...and {len(failures) - 3} more"
            self.message_user(
                request,
                f"Some memberships could not be promoted: {preview}",
                level=messages.WARNING,
            )
