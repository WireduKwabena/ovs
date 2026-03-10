"""Audit event contract definitions."""

from __future__ import annotations


GOVERNMENT_POSITION_CREATED_EVENT = "government_position_created"
GOVERNMENT_POSITION_UPDATED_EVENT = "government_position_updated"
GOVERNMENT_POSITION_DELETED_EVENT = "government_position_deleted"

PERSONNEL_RECORD_CREATED_EVENT = "personnel_record_created"
PERSONNEL_RECORD_UPDATED_EVENT = "personnel_record_updated"
PERSONNEL_RECORD_DELETED_EVENT = "personnel_record_deleted"
PERSONNEL_LINKED_CANDIDATE_EVENT = "personnel_linked_candidate"

APPOINTMENT_RECORD_CREATED_EVENT = "appointment_record_created"
APPOINTMENT_RECORD_UPDATED_EVENT = "appointment_record_updated"
APPOINTMENT_RECORD_DELETED_EVENT = "appointment_record_deleted"
APPOINTMENT_NOMINATION_CREATED_EVENT = "appointment_nomination_created"
APPOINTMENT_STAGE_TRANSITION_EVENT = "appointment_stage_transition"
APPOINTMENT_STAGE_ACTION_TAKEN_EVENT = "appointment_stage_action_taken"
APPOINTMENT_FINAL_DECISION_RECORDED_EVENT = "appointment_final_decision_recorded"
APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT = "appointment_vetting_linkage_ensured"
APPOINTMENT_PUBLICATION_PUBLISHED_EVENT = "appointment_publication_published"
APPOINTMENT_PUBLICATION_REVOKED_EVENT = "appointment_publication_revoked"
VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT = "vetting_decision_recommendation_generated"
VETTING_DECISION_OVERRIDE_RECORDED_EVENT = "vetting_decision_override_recorded"
VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT = "verification_gateway_request_created"
VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT = "verification_gateway_result_recorded"

GOVERNMENT_AUDIT_EVENT_CATALOG: list[dict[str, str]] = [
    {
        "key": GOVERNMENT_POSITION_CREATED_EVENT,
        "entity_type": "GovernmentPosition",
        "action": "create",
        "description": "Government position created.",
    },
    {
        "key": GOVERNMENT_POSITION_UPDATED_EVENT,
        "entity_type": "GovernmentPosition",
        "action": "update",
        "description": "Government position updated.",
    },
    {
        "key": GOVERNMENT_POSITION_DELETED_EVENT,
        "entity_type": "GovernmentPosition",
        "action": "delete",
        "description": "Government position deleted.",
    },
    {
        "key": PERSONNEL_RECORD_CREATED_EVENT,
        "entity_type": "PersonnelRecord",
        "action": "create",
        "description": "Personnel record created.",
    },
    {
        "key": PERSONNEL_RECORD_UPDATED_EVENT,
        "entity_type": "PersonnelRecord",
        "action": "update",
        "description": "Personnel record updated.",
    },
    {
        "key": PERSONNEL_RECORD_DELETED_EVENT,
        "entity_type": "PersonnelRecord",
        "action": "delete",
        "description": "Personnel record deleted.",
    },
    {
        "key": PERSONNEL_LINKED_CANDIDATE_EVENT,
        "entity_type": "PersonnelRecord",
        "action": "update",
        "description": "Personnel record linked to a candidate profile.",
    },
    {
        "key": APPOINTMENT_RECORD_CREATED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "create",
        "description": "Appointment record created.",
    },
    {
        "key": APPOINTMENT_RECORD_UPDATED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment record updated.",
    },
    {
        "key": APPOINTMENT_RECORD_DELETED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "delete",
        "description": "Appointment record deleted.",
    },
    {
        "key": APPOINTMENT_NOMINATION_CREATED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "create",
        "description": "Appointment nomination created and registered.",
    },
    {
        "key": APPOINTMENT_STAGE_TRANSITION_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment record moved to another stage/status.",
    },
    {
        "key": APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment stage action captured with actor and stage context.",
    },
    {
        "key": APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment final decision recorded (appointed/rejected).",
    },
    {
        "key": APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment record ensured to have vetting linkage.",
    },
    {
        "key": APPOINTMENT_PUBLICATION_PUBLISHED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment record publication was published.",
    },
    {
        "key": APPOINTMENT_PUBLICATION_REVOKED_EVENT,
        "entity_type": "AppointmentRecord",
        "action": "update",
        "description": "Appointment record publication was revoked.",
    },
    {
        "key": VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT,
        "entity_type": "VettingDecisionRecommendation",
        "action": "create",
        "description": "Vetting decision recommendation generated from rubric/policy/evidence signals.",
    },
    {
        "key": VETTING_DECISION_OVERRIDE_RECORDED_EVENT,
        "entity_type": "VettingDecisionRecommendation",
        "action": "update",
        "description": "Human override recorded for a vetting decision recommendation.",
    },
    {
        "key": VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT,
        "entity_type": "VerificationRequest",
        "action": "create",
        "description": "External verification request created for inter-agency evidence collection.",
    },
    {
        "key": VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT,
        "entity_type": "ExternalVerificationResult",
        "action": "create",
        "description": "External verification result recorded as advisory evidence input.",
    },
]

__all__ = [
    "APPOINTMENT_FINAL_DECISION_RECORDED_EVENT",
    "APPOINTMENT_NOMINATION_CREATED_EVENT",
    "APPOINTMENT_PUBLICATION_PUBLISHED_EVENT",
    "APPOINTMENT_PUBLICATION_REVOKED_EVENT",
    "APPOINTMENT_STAGE_ACTION_TAKEN_EVENT",
    "APPOINTMENT_STAGE_TRANSITION_EVENT",
    "APPOINTMENT_RECORD_CREATED_EVENT",
    "APPOINTMENT_RECORD_DELETED_EVENT",
    "APPOINTMENT_RECORD_UPDATED_EVENT",
    "APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT",
    "GOVERNMENT_AUDIT_EVENT_CATALOG",
    "VETTING_DECISION_OVERRIDE_RECORDED_EVENT",
    "VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT",
    "GOVERNMENT_POSITION_CREATED_EVENT",
    "GOVERNMENT_POSITION_DELETED_EVENT",
    "GOVERNMENT_POSITION_UPDATED_EVENT",
    "PERSONNEL_RECORD_CREATED_EVENT",
    "PERSONNEL_RECORD_DELETED_EVENT",
    "PERSONNEL_LINKED_CANDIDATE_EVENT",
    "PERSONNEL_RECORD_UPDATED_EVENT",
    "VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT",
    "VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT",
]
