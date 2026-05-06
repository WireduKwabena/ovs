"""Database models for admin_dashboard."""

import uuid

from django.conf import settings
from django.db import models


class PlatformIssueReport(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

	CATEGORY_BUG = "bug"
	CATEGORY_ISSUE = "issue"
	CATEGORY_IMPROVEMENT = "improvement"
	CATEGORY_CHOICES = [
		(CATEGORY_BUG, "Bug"),
		(CATEGORY_ISSUE, "Issue"),
		(CATEGORY_IMPROVEMENT, "Improvement"),
	]

	SEVERITY_LOW = "low"
	SEVERITY_MEDIUM = "medium"
	SEVERITY_HIGH = "high"
	SEVERITY_CRITICAL = "critical"
	SEVERITY_CHOICES = [
		(SEVERITY_LOW, "Low"),
		(SEVERITY_MEDIUM, "Medium"),
		(SEVERITY_HIGH, "High"),
		(SEVERITY_CRITICAL, "Critical"),
	]

	STATUS_OPEN = "open"
	STATUS_IN_PROGRESS = "in_progress"
	STATUS_RESOLVED = "resolved"
	STATUS_CHOICES = [
		(STATUS_OPEN, "Open"),
		(STATUS_IN_PROGRESS, "In Progress"),
		(STATUS_RESOLVED, "Resolved"),
	]

	title = models.CharField(max_length=200)
	description = models.TextField()
	steps_to_reproduce = models.TextField(blank=True)
	page_url = models.CharField(max_length=500, blank=True)
	browser_info = models.CharField(max_length=500, blank=True)

	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_ISSUE)
	severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)

	reporter = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="platform_issue_reports",
		db_constraint=False,
	)
	resolved_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		related_name="resolved_platform_issue_reports",
		null=True,
		blank=True,
		db_constraint=False,
	)
	resolved_at = models.DateTimeField(null=True, blank=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["status", "created_at"]),
			models.Index(fields=["severity", "created_at"]),
			models.Index(fields=["reporter", "created_at"]),
		]

	def __str__(self) -> str:
		return f"{self.title} ({self.status})"
