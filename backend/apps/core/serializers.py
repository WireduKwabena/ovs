from rest_framework import serializers


class SystemHealthCheckSerializer(serializers.Serializer):
    ok = serializers.BooleanField(allow_null=True)
    configured = serializers.BooleanField(required=False)
    error = serializers.CharField(required=False)


class SystemHealthChecksSerializer(serializers.Serializer):
    database = SystemHealthCheckSerializer()
    redis = SystemHealthCheckSerializer()
    celery_broker = SystemHealthCheckSerializer()


class SystemHealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    strict_runtime_checks = serializers.BooleanField()
    checks = SystemHealthChecksSerializer()
    failures = serializers.ListField(child=serializers.CharField())
