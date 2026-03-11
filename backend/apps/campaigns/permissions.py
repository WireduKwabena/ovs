from apps.core.permissions import IsGovernmentWorkflowOperator


class IsInternalWorkflowOperator(IsGovernmentWorkflowOperator):
    message = "Only authorized internal workflow actors can access campaigns."
