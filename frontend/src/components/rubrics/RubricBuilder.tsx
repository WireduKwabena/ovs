// src/components/rubrics/RubricBuilder.tsx
import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type UniqueIdentifier,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, X, Plus, Save, AlertCircle, FileText, Info } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { rubricService } from '@/services/rubric.service';
import type { CreateRubricData, RubricCriteriaType, RubricScoringMethod, RubricType } from '@/types';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { HelpTooltip, FieldLabel } from '@/components/common/FieldHelp';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'react-toastify';

interface BuilderCriterion {
  id: string;
  name: string;
  description: string;
  criteria_type: RubricCriteriaType;
  scoring_method: RubricScoringMethod;
  weight: number;
  minimum_score: number;
  is_mandatory: boolean;
  evaluation_guidelines: string;
  display_order: number;
}

interface RubricDraft extends CreateRubricData {
  criteria: BuilderCriterion[];
}

interface SortableCriterionProps {
  id: UniqueIdentifier;
  criterion: BuilderCriterion;
  updateCriterion: (id: string, field: keyof BuilderCriterion, value: any) => void;
  removeCriterion: (id: string) => void;
  criteriaTypes: { value: string; label: string; icon: string }[];
}

// SortableItem component using useSortable hook
function SortableCriterion({ id, criterion, updateCriterion, removeCriterion, criteriaTypes }: SortableCriterionProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 'auto',
    opacity: isDragging ? 0.8 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-gray-50 rounded-lg p-4 border-2 border-dashed border-slate-700"
    >
      <div className="flex items-start gap-4">
        <div {...attributes} {...listeners} className="shrink-0 mt-1 cursor-grab active:cursor-grabbing">
          <GripVertical className="w-5 h-5 text-slate-700" />
        </div>

        <div className="flex-1">
          <div className="mb-3">
            <FieldLabel
              htmlFor={`criterion-name-${criterion.id}`}
              label="Criterion Name"
              required
              help="Clear criterion names make scoring intent obvious to reviewers and AI-generated reports."
            />
            <input
              id={`criterion-name-${criterion.id}`}
              type="text"
              value={criterion.name}
              onChange={(e) => updateCriterion(criterion.id, 'name', e.target.value)}
              placeholder="Criterion name"
              className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <FieldLabel
                label="Type"
                help="Use type to map the criterion to the right scoring domain (document, consistency, interview, etc.)."
              />
              <Select value={criterion.criteria_type} onValueChange={(value) => updateCriterion(criterion.id, 'criteria_type', value)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {criteriaTypes.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <FieldLabel
                htmlFor={`criterion-weight-${criterion.id}`}
                label="Weight (%)"
                help="Criterion weight controls relative influence in final rubric scoring."
              />
              <Input
                id={`criterion-weight-${criterion.id}`}
                type="number"
                value={criterion.weight}
                onChange={(e) => updateCriterion(criterion.id, 'weight', parseInt(e.target.value))}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <FieldLabel
                htmlFor={`criterion-min-score-${criterion.id}`}
                label="Min Score (%)"
                help="If score falls below this threshold, this criterion is treated as underperforming."
              />
              <Input
                id={`criterion-min-score-${criterion.id}`}
                type="number"
                value={criterion.minimum_score}
                onChange={(e) => updateCriterion(criterion.id, 'minimum_score', parseInt(e.target.value))}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 pt-8">
              <Input
                id={`criterion-mandatory-${criterion.id}`}
                type="checkbox"
                checked={criterion.is_mandatory}
                onChange={(e) => updateCriterion(criterion.id, 'is_mandatory', e.target.checked)}
                className="w-5 h-5 text-blue-600 rounded"
              />
              <label htmlFor={`criterion-mandatory-${criterion.id}`} className="text-sm font-medium text-slate-800">
                Mandatory
              </label>
              <HelpTooltip text="Mandatory criteria should not be skipped during manual review and are usually key risk controls." />
            </div>
          </div>
        </div>

        {/* Delete Button */}
        <Button
          onClick={() => removeCriterion(criterion.id)}
          className="mt-2 p-2 text-red-600 hover:bg-red-50 rounded-lg"
        >
          <X className="w-5 h-5" />
        </Button>
      </div>
    </div>
  );
}

export function RubricBuilder() {
  const navigate = useNavigate();
  const { rubricId } = useParams<{ rubricId?: string }>();
  const isEditMode = Boolean(rubricId);
  const [rubric, setRubric] = useState<RubricDraft>({
    name: '',
    description: '',
    rubric_type: 'general',
    document_authenticity_weight: 25,
    consistency_weight: 20,
    fraud_detection_weight: 20,
    interview_weight: 25,
    manual_review_weight: 10,
    passing_score: 70,
    auto_approve_threshold: 90,
    auto_reject_threshold: 40,
    minimum_document_score: 60,
    maximum_fraud_score: 50,
    require_interview: true,
    critical_flags_auto_fail: true,
    max_unresolved_flags: 2,
    is_active: true,
    is_default: false,
    criteria: [],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  const rubricTypes = useMemo(() => [
    { value: 'general', label: 'General Purpose' },
    { value: 'technical', label: 'Technical Position' },
    { value: 'executive', label: 'Executive Level' },
    { value: 'sensitive', label: 'High-Security Position' },
    { value: 'custom', label: 'Custom' },
  ], []);

  const criteriaTypes = useMemo(() => [
    { value: 'document', label: 'Document Quality', icon: '📄' },
    { value: 'consistency', label: 'Data Consistency', icon: '🔗' },
    { value: 'interview', label: 'Interview Performance', icon: '🎤' },
    { value: 'behavioral', label: 'Behavioral Assessment', icon: '🧠' },
    { value: 'technical', label: 'Technical Competency', icon: '⚙️' },
    { value: 'custom', label: 'Custom Criterion', icon: '🧩' },
  ], []);

  const addCriterion = useCallback(() => {
    const newCriterion: BuilderCriterion = {
      id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `criterion-${Date.now()}`,
      name: '',
      description: '',
      criteria_type: 'document',
      scoring_method: 'ai_score',
      weight: 10,
      minimum_score: 70,
      is_mandatory: false,
      evaluation_guidelines: '',
      display_order: rubric.criteria.length,
    };
    setRubric((prev) => ({ ...prev, criteria: [...prev.criteria, newCriterion] }));
  }, [rubric.criteria.length]);

  const updateCriterion = useCallback((id: string, field: keyof BuilderCriterion, value: any) => {
    setRubric((prev) => ({
      ...prev,
      criteria: prev.criteria.map((c) =>
        c.id === id ? { ...c, [field]: value } : c
      ),
    }));
  }, []);

  const removeCriterion = useCallback((id: string) => {
    setRubric((prev) => ({
      ...prev,
      criteria: prev.criteria.filter((c) => c.id !== id),
    }));
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setRubric((prev) => {
        const oldIndex = prev.criteria.findIndex((c) => c.id === active.id);
        const newIndex = prev.criteria.findIndex((c) => c.id === over.id);
        const reorderedCriteria = arrayMove(prev.criteria, oldIndex, newIndex);
        const updatedCriteria = reorderedCriteria.map((criterion, index) => ({
          ...criterion,
          display_order: index,
        }));
        return { ...prev, criteria: updatedCriteria };
      });
    }
  }, []);

  const validateRubric = useCallback(() => {
    const nextErrors: Record<string, string> = {};
    const componentWeightTotal =
      rubric.document_authenticity_weight +
      rubric.consistency_weight +
      rubric.fraud_detection_weight +
      rubric.interview_weight +
      rubric.manual_review_weight;

    if (!rubric.name.trim()) {
      nextErrors.name = 'Rubric name is required.';
    }
    if (componentWeightTotal !== 100) {
      nextErrors.weights = `Component weights must sum to 100% (current: ${componentWeightTotal}%).`;
    }
    if (!rubric.criteria.length) {
      nextErrors.criteria = 'Add at least one criterion.';
    }
    const invalidCriterion = rubric.criteria.some(
      (criterion) =>
        !criterion.name.trim() ||
        criterion.weight < 0 ||
        criterion.weight > 100 ||
        criterion.minimum_score < 0 ||
        criterion.minimum_score > 100,
    );
    if (invalidCriterion) {
      nextErrors.criteria_detail = 'Each criterion needs a name and valid weight/minimum score.';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }, [rubric]);

  const saveRubric = useCallback(async () => {
    if (!validateRubric()) return;

    setSaving(true);
    try {
      const payload: CreateRubricData = {
        name: rubric.name.trim(),
        description: rubric.description.trim(),
        rubric_type: rubric.rubric_type,
        document_authenticity_weight: rubric.document_authenticity_weight,
        consistency_weight: rubric.consistency_weight,
        fraud_detection_weight: rubric.fraud_detection_weight,
        interview_weight: rubric.interview_weight,
        manual_review_weight: rubric.manual_review_weight,
        passing_score: rubric.passing_score,
        auto_approve_threshold: rubric.auto_approve_threshold,
        auto_reject_threshold: rubric.auto_reject_threshold,
        minimum_document_score: rubric.minimum_document_score,
        maximum_fraud_score: rubric.maximum_fraud_score,
        require_interview: rubric.require_interview,
        critical_flags_auto_fail: rubric.critical_flags_auto_fail,
        max_unresolved_flags: rubric.max_unresolved_flags,
        is_active: rubric.is_active,
        is_default: rubric.is_default,
      };

      const savedRubric = rubricId
        ? await rubricService.update(rubricId, payload)
        : await rubricService.create(payload);

      const existingCriteria = rubricId
        ? await rubricService.listCriteria({ rubric: rubricId })
        : [];
      const existingIds = new Set(existingCriteria.map((criterion) => criterion.id));
      const keptIds = new Set<string>();

      for (const [index, criterion] of rubric.criteria.entries()) {
        const criteriaPayload = {
          name: criterion.name.trim(),
          description: criterion.description.trim(),
          criteria_type: criterion.criteria_type,
          scoring_method: criterion.scoring_method,
          weight: criterion.weight,
          minimum_score: criterion.minimum_score,
          is_mandatory: criterion.is_mandatory,
          evaluation_guidelines: criterion.evaluation_guidelines.trim(),
          display_order: index,
        };

        if (typeof criterion.id === 'string' && existingIds.has(criterion.id)) {
          await rubricService.updateCriteria(criterion.id, criteriaPayload);
          keptIds.add(criterion.id);
          continue;
        }

        const createdCriterion = await rubricService.addCriteria(savedRubric.id, criteriaPayload);
        keptIds.add(createdCriterion.id);
      }

      for (const existingCriterion of existingCriteria) {
        if (!keptIds.has(existingCriterion.id)) {
          await rubricService.deleteCriteria(existingCriterion.id);
        }
      }

      toast.success(isEditMode ? 'Rubric updated successfully.' : 'Rubric saved successfully.');
      navigate('/rubrics');
    } catch (error: any) {
      toast.error(error?.message || 'Failed to save rubric');
    } finally {
      setSaving(false);
    }
  }, [rubric, validateRubric, navigate, rubricId, isEditMode]);

  const weightValid =
    rubric.document_authenticity_weight +
      rubric.consistency_weight +
      rubric.fraud_detection_weight +
      rubric.interview_weight +
      rubric.manual_review_weight ===
    100;
  const criteriaIds = useMemo(() => rubric.criteria.map((c) => c.id), [rubric.criteria]);

  useEffect(() => {
    if (!rubricId) {
      return;
    }

    let isMounted = true;
    const loadRubricForEdit = async () => {
      setLoading(true);
      try {
        const [rubricDetail, rubricCriteria] = await Promise.all([
          rubricService.getById(rubricId),
          rubricService.listCriteria({ rubric: rubricId }),
        ]);
        if (!isMounted) return;

        setRubric({
          name: rubricDetail.name,
          description: rubricDetail.description ?? '',
          rubric_type: rubricDetail.rubric_type,
          document_authenticity_weight: rubricDetail.document_authenticity_weight,
          consistency_weight: rubricDetail.consistency_weight,
          fraud_detection_weight: rubricDetail.fraud_detection_weight,
          interview_weight: rubricDetail.interview_weight,
          manual_review_weight: rubricDetail.manual_review_weight,
          passing_score: rubricDetail.passing_score,
          auto_approve_threshold: rubricDetail.auto_approve_threshold,
          auto_reject_threshold: rubricDetail.auto_reject_threshold,
          minimum_document_score: rubricDetail.minimum_document_score,
          maximum_fraud_score: rubricDetail.maximum_fraud_score,
          require_interview: rubricDetail.require_interview,
          critical_flags_auto_fail: rubricDetail.critical_flags_auto_fail,
          max_unresolved_flags: rubricDetail.max_unresolved_flags,
          is_active: rubricDetail.is_active,
          is_default: rubricDetail.is_default,
          criteria: rubricCriteria
            .sort((a, b) => a.display_order - b.display_order)
            .map((criterion) => ({
              id: criterion.id,
              name: criterion.name,
              description: criterion.description ?? '',
              criteria_type: criterion.criteria_type,
              scoring_method: criterion.scoring_method,
              weight: criterion.weight,
              minimum_score: criterion.minimum_score ?? 0,
              is_mandatory: criterion.is_mandatory,
              evaluation_guidelines: criterion.evaluation_guidelines ?? '',
              display_order: criterion.display_order,
            })),
        });
      } catch {
        toast.error('Unable to load rubric for editing.');
        navigate('/rubrics');
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadRubricForEdit();
    return () => {
      isMounted = false;
    };
  }, [navigate, rubricId]);

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center text-slate-700">
        Loading rubric...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-6">
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h1 className="text-3xl font-bold mb-6">{isEditMode ? 'Edit Rubric' : 'Create New Rubric'}</h1>
          <div className="mb-6 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            Hover or focus the <Info className="mx-1 inline h-4 w-4 align-text-bottom" /> icons beside labels to see field guidance.
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div>
              <FieldLabel
                htmlFor="rubric-name"
                label="Name"
                required
                help="Use a name that reflects hiring context, e.g. 'Engineering Mid-Level Vetting Rubric'."
              />
              <input
                id="rubric-name"
                type="text"
                value={rubric.name}
                onChange={(e) => setRubric({ ...rubric, name: e.target.value })}
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter rubric name"
              />
            </div>
            
            <div>
              <FieldLabel
                label="Type"
                required
                help="Rubric type helps teams quickly choose an appropriate scoring model for the campaign."
              />
              <Select value={rubric.rubric_type} onValueChange={(value) => setRubric({ ...rubric, rubric_type: value as RubricType })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Rubric Types</SelectLabel>
                    {rubricTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <FieldLabel
                htmlFor="rubric-passing-score"
                label="Passing Score (%)"
                required
                help="Candidates at or above this total weighted score are marked as passing."
              />
              <Input
                id="rubric-passing-score"
                type="number"
                value={rubric.passing_score}
                onChange={(e) => setRubric({ ...rubric, passing_score: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <FieldLabel
                htmlFor="rubric-auto-approve-threshold"
                label="Auto Approve (%)"
                help="Candidates above this score can be auto-approved when no hard-fail conditions apply."
              />
              <Input
                id="rubric-auto-approve-threshold"
                type="number"
                value={rubric.auto_approve_threshold}
                onChange={(e) => setRubric({ ...rubric, auto_approve_threshold: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="md:col-span-3">
              <FieldLabel
                htmlFor="rubric-description"
                label="Description"
                help="Describe intended usage, business unit, and any reviewer notes for this rubric."
              />
            </div>
            <textarea
              id="rubric-description"
              value={rubric.description}
              onChange={(e) => setRubric({ ...rubric, description: e.target.value })}
              placeholder="Rubric description (optional)"
              rows={4}
              className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 md:col-span-3"
            />
            
            <div>
              <FieldLabel
                htmlFor="rubric-auto-reject-threshold"
                label="Auto Reject (%)"
                help="Candidates below this score can be auto-rejected, subject to your process policy."
              />
              <Input
                id="rubric-auto-reject-threshold"
                type="number"
                value={rubric.auto_reject_threshold}
                onChange={(e) => setRubric({ ...rubric, auto_reject_threshold: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <FieldLabel
                htmlFor="rubric-minimum-document-score"
                label="Min Document (%)"
                help="Hard floor for document authenticity quality before proceeding."
              />
              <Input
                id="rubric-minimum-document-score"
                type="number"
                value={rubric.minimum_document_score}
                onChange={(e) => setRubric({ ...rubric, minimum_document_score: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <FieldLabel
                htmlFor="rubric-max-fraud-score"
                label="Max Fraud (%)"
                help="Maximum allowed fraud-risk score before automatic escalation or rejection."
              />
              <Input
                id="rubric-max-fraud-score"
                type="number"
                value={rubric.maximum_fraud_score}
                onChange={(e) => setRubric({ ...rubric, maximum_fraud_score: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <FieldLabel
                htmlFor="rubric-max-unresolved-flags"
                label="Max Unresolved Flags"
                help="Upper limit for unresolved risk flags allowed before forcing manual review."
              />
              <Input
                id="rubric-max-unresolved-flags"
                type="number"
                value={rubric.max_unresolved_flags}
                onChange={(e) => setRubric({ ...rubric, max_unresolved_flags: Number(e.target.value) || 0 })}
                min="0"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-800">
              <Input
                id="rubric-require-interview"
                type="checkbox"
                checked={rubric.require_interview}
                onChange={(e) => setRubric({ ...rubric, require_interview: e.target.checked })}
                className="w-4 h-4"
              />
              <label htmlFor="rubric-require-interview">Require Interview</label>
              <HelpTooltip text="If enabled, interview scoring is expected before finalizing candidate outcome." />
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-800">
              <Input
                id="rubric-critical-flags-auto-fail"
                type="checkbox"
                checked={rubric.critical_flags_auto_fail}
                onChange={(e) => setRubric({ ...rubric, critical_flags_auto_fail: e.target.checked })}
                className="w-4 h-4"
              />
              <label htmlFor="rubric-critical-flags-auto-fail">Auto-fail Critical Flags</label>
              <HelpTooltip text="Immediately fail candidates with critical fraud or integrity flags." />
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-800">
              <Input
                id="rubric-is-active"
                type="checkbox"
                checked={rubric.is_active}
                onChange={(e) => setRubric({ ...rubric, is_active: e.target.checked })}
                className="w-4 h-4"
              />
              <label htmlFor="rubric-is-active">Active Rubric</label>
              <HelpTooltip text="Only active rubrics should be used in new campaign evaluations." />
            </div>
          </div>

          <div className="mb-2 flex items-center gap-1.5">
            <p className="block text-sm font-medium text-slate-800">Component Weights (%)</p>
            <HelpTooltip text="These five inputs must total 100%. They control how each scoring block contributes to the final weighted score." />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-4">
            <div>
              <FieldLabel label="Document" help="Weight for document authenticity and tamper checks." />
              <Input
                type="number"
                value={rubric.document_authenticity_weight}
                onChange={(e) => setRubric({ ...rubric, document_authenticity_weight: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="border border-slate-700"
                aria-label="Document component weight"
              />
            </div>
            <div>
              <FieldLabel label="Consistency" help="Weight for cross-document and data consistency checks." />
              <Input
                type="number"
                value={rubric.consistency_weight}
                onChange={(e) => setRubric({ ...rubric, consistency_weight: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="border border-slate-700"
                aria-label="Consistency component weight"
              />
            </div>
            <div>
              <FieldLabel label="Fraud" help="Weight for fraud and anomaly risk scoring." />
              <Input
                type="number"
                value={rubric.fraud_detection_weight}
                onChange={(e) => setRubric({ ...rubric, fraud_detection_weight: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="border border-slate-700"
                aria-label="Fraud component weight"
              />
            </div>
            <div>
              <FieldLabel label="Interview" help="Weight for interview quality and response assessment." />
              <Input
                type="number"
                value={rubric.interview_weight}
                onChange={(e) => setRubric({ ...rubric, interview_weight: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="border border-slate-700"
                aria-label="Interview component weight"
              />
            </div>
            <div>
              <FieldLabel label="Manual" help="Weight for manual reviewer override or discretionary scoring." />
              <Input
                type="number"
                value={rubric.manual_review_weight}
                onChange={(e) => setRubric({ ...rubric, manual_review_weight: Number(e.target.value) || 0 })}
                min="0"
                max="100"
                className="border border-slate-700"
                aria-label="Manual component weight"
              />
            </div>
          </div>
          <p className="text-xs text-slate-700">
            Weights must sum to exactly 100%. {weightValid ? 'Current total is valid.' : 'Current total is invalid.'}
          </p>
        </div>
        
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-1.5">
              <h2 className="text-xl font-bold">Criteria ({rubric.criteria.length})</h2>
              <HelpTooltip text="Criteria define specific checks that feed into the rubric decision. Drag handles let you reorder for reviewer readability." />
            </div>
            <button
              onClick={addCriterion}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              Add Criterion
            </button>
          </div>
          
          {rubric.criteria.length === 0 ? (
            <div className="text-center py-12 text-slate-700">
              <FileText className="w-12 h-12 mx-auto mb-4 text-slate-700" />
              <p className="text-lg">No criteria added yet</p>
              <p className="text-sm">Add criteria to define evaluation rules</p>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={criteriaIds}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-4">
                  {rubric.criteria.map((criterion) => (
                    <SortableCriterion
                      key={criterion.id}
                      id={criterion.id}
                      criterion={criterion}
                      updateCriterion={updateCriterion}
                      removeCriterion={removeCriterion}
                      criteriaTypes={criteriaTypes}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>
        
        <div className="flex justify-end gap-4">
          <button
            onClick={() => navigate('/rubrics')}
            className="px-6 py-3 border-2 border-slate-700 text-slate-800 rounded-lg hover:bg-slate-100 font-semibold"
          >
            Cancel
          </button>
          <button
            onClick={saveRubric}
            disabled={saving || !weightValid}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                {isEditMode ? 'Update Rubric' : 'Save Rubric'}
              </>
            )}
          </button>
        </div>
        
        {Object.keys(errors).length > 0 && (
          <div className="mt-4 p-4 bg-amber-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertCircle className="w-5 h-5" />
              <span>{Object.values(errors).join(' ')}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

