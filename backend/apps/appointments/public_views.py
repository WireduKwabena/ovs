"""Dedicated read-only public transparency endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .public_serializers import (
    PublicAppointmentRecordSerializer,
    PublicGovernmentPositionSerializer,
    PublicPersonnelRecordSerializer,
    PublicTransparencySummarySerializer,
)
from .public_services import (
    apply_public_appointment_query_params,
    build_public_transparency_summary,
    public_officeholders_queryset,
    public_open_appointments_queryset,
    public_positions_queryset,
    public_vacant_positions_queryset,
    published_appointments_queryset,
)


class PublicTransparencySummaryView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        payload = build_public_transparency_summary()
        serializer = PublicTransparencySummarySerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyAppointmentListView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = published_appointments_queryset()
        queryset = apply_public_appointment_query_params(queryset, query_params=request.query_params)
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyGazetteFeedView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = published_appointments_queryset(require_gazette_number=True)
        queryset = apply_public_appointment_query_params(queryset, query_params=request.query_params)
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyOpenAppointmentListView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = public_open_appointments_queryset()
        queryset = apply_public_appointment_query_params(queryset, query_params=request.query_params)
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyAppointmentDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request, appointment_id):
        queryset = published_appointments_queryset()
        appointment = get_object_or_404(queryset, id=appointment_id)
        serializer = PublicAppointmentRecordSerializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyPositionListView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = public_positions_queryset()
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyVacantPositionListView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = public_vacant_positions_queryset()
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicTransparencyOfficeholderListView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        queryset = public_officeholders_queryset()
        serializer = PublicPersonnelRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
