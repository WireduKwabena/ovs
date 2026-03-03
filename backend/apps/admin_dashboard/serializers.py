from rest_framework import serializers
from apps.applications.models import VettingCase
from apps.authentication.models import User


class VettingCaseAdminSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.CharField(source='applicant.email')
    application_type = serializers.CharField(source="position_applied")
    admin = serializers.SerializerMethodField()

    class Meta:
        model = VettingCase
        fields = [
            'id',
            'case_id',
            'applicant_name',
            'applicant_email',
            'status',
            'application_type',
            'priority',
            'consistency_score',
            'fraud_risk_score',
            'created_at',
            'updated_at',
            'admin',
        ]

    def get_applicant_name(self, obj) -> str:
        return (
            obj.applicant.get_full_name()
            if hasattr(obj.applicant, "get_full_name")
            else obj.applicant.email
        )

    def get_admin(self, obj) -> str | None:
        assignee = getattr(obj, "assigned_to", None)
        if not assignee:
            return None
        return assignee.get_full_name() if hasattr(assignee, "get_full_name") else assignee.email


class DashboardRecentApplicationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    case_id = serializers.CharField()
    applicant_name = serializers.CharField()
    application_type = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    rubric_score = serializers.FloatField(allow_null=True)


class DashboardDocumentsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    verified = serializers.IntegerField()
    verification_rate = serializers.FloatField()


class DashboardFraudSerializer(serializers.Serializer):
    total_scans = serializers.IntegerField()
    high_risk_count = serializers.IntegerField()
    high_risk_rate = serializers.FloatField()


class DashboardTrendsSerializer(serializers.Serializer):
    monthly_applications = serializers.IntegerField()
    avg_consistency_score = serializers.FloatField()


class AdminDashboardResponseSerializer(serializers.Serializer):
    total_applications = serializers.IntegerField()
    pending = serializers.IntegerField()
    under_review = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    recent_applications = DashboardRecentApplicationSerializer(many=True)
    documents = DashboardDocumentsSerializer()
    fraud_detection = DashboardFraudSerializer()
    trends = DashboardTrendsSerializer()


class DistributionItemSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    status = serializers.CharField(required=False)
    position_applied = serializers.CharField(required=False)
    priority = serializers.CharField(required=False)


class RubricStatisticsSerializer(serializers.Serializer):
    avg_score = serializers.FloatField(allow_null=True)
    pass_count = serializers.IntegerField()
    fail_count = serializers.IntegerField()


class MonthlyTrendItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    count = serializers.IntegerField()


class AdminAnalyticsResponseSerializer(serializers.Serializer):
    status_distribution = DistributionItemSerializer(many=True)
    type_distribution = DistributionItemSerializer(many=True)
    priority_distribution = DistributionItemSerializer(many=True)
    rubric_statistics = RubricStatisticsSerializer()
    monthly_trend = MonthlyTrendItemSerializer(many=True)
    total_applications = serializers.IntegerField()
    total_users = serializers.IntegerField()


class AdminCasesResponseSerializer(serializers.Serializer):
    results = VettingCaseAdminSerializer(many=True)
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    ordering = serializers.CharField(required=False)


class AdminManagedUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "user_type",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_two_factor_enabled",
            "last_login",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj) -> str:
        if hasattr(obj, "get_full_name"):
            return obj.get_full_name()
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email


class AdminUsersResponseSerializer(serializers.Serializer):
    results = AdminManagedUserSerializer(many=True)
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    ordering = serializers.CharField(required=False)


class AdminUserUpdateRequestSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    reset_two_factor = serializers.BooleanField(required=False, default=False)

