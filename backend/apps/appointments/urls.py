from rest_framework.routers import DefaultRouter

from .views import AppointmentRecordViewSet, ApprovalStageTemplateViewSet, ApprovalStageViewSet

router = DefaultRouter()
router.register(r"records", AppointmentRecordViewSet, basename="appointment-record")
router.register(r"stage-templates", ApprovalStageTemplateViewSet, basename="approval-stage-template")
router.register(r"stages", ApprovalStageViewSet, basename="approval-stage")

urlpatterns = router.urls
