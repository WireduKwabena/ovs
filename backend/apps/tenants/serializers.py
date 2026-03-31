from rest_framework import serializers

from .models import Domain, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "code",
            "name",
            "organization_type",
            "is_active",
            "tier",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["domain", "is_primary"]


class CreateOrganizationAdminSerializer(serializers.Serializer):
    """Serializer for bootstrapping the first admin user for an organization."""
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
