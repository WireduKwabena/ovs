from rest_framework import serializers
from .models import Organization



class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "code",
            "name",
            "organization_type",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['domain', 'is_primary']
        

    

class CreateOrganizationAdminSerializer(serializers.Serializer):
    # serializer for creating first admin user for an organization