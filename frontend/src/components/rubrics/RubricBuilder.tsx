// src/components/rubrics/RubricBuilder.tsx
import { useState, useCallback, useMemo } from 'react';
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
import { GripVertical, X, Plus, Save, AlertCircle, FileText } from 'lucide-react';
import { useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import type { AppDispatch } from '@/app/store';
import { createRubric } from '@/store/rubricSlice';
import type { ApplicationType, RubricCriteria, VettingRubric } from '@/types';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'react-toastify';

interface SortableCriterionProps {
  id: UniqueIdentifier;
  criterion: RubricCriteria;
  updateCriterion: (id: number, field: keyof RubricCriteria, value: any) => void;
  removeCriterion: (id: number) => void;
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
          <div className="flex items-center justify-between mb-3">
            <input
              type="text"
              value={criterion.name}
              onChange={(e) => updateCriterion(criterion.id, 'name', e.target.value)}
              placeholder="Criterion name"
              className="flex-1 px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="block text-xs font-medium text-slate-800 mb-1">Type</p>
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
              <label htmlFor={`criterion-weight-${criterion.id}`} className="block text-xs font-medium text-slate-800 mb-1">
                Weight (%)
              </label>
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
              <label htmlFor={`criterion-min-score-${criterion.id}`} className="block text-xs font-medium text-slate-800 mb-1">
                Min Score (%)
              </label>
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

            <div className="flex items-center gap-2">
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
  const dispatch = useDispatch<AppDispatch>();
  const [rubric, setRubric] = useState<Omit<VettingRubric, 'id' | 'created_at' | 'updated_at'>>({
    name: '',
    description: '',
    rubric_type: 'employment',
    department: '',
    position_level: '',
    passing_score: 70,
    auto_approve_threshold: 90,
    auto_reject_threshold: 50,
    criteria: [],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const criteriaTypes = useMemo(() => [
    { value: 'document_authenticity', label: 'Document Authenticity', icon: '📄' },
    { value: 'ocr_confidence', label: 'OCR Quality', icon: '🔤' },
    { value: 'data_consistency', label: 'Data Consistency', icon: '🔗' },
    { value: 'fraud_score', label: 'Fraud Risk', icon: '⚠️' },
    { value: 'credential_validity', label: 'Credential Validity', icon: '🎓' },
    { value: 'experience_years', label: 'Years of Experience', icon: '💼' },
    { value: 'education_level', label: 'Education Level', icon: '📚' },
  ], []);

  const addCriterion = useCallback(() => {
    const newCriterion: RubricCriteria = {
      id: Date.now(),
      name: '',
      criteria_type: 'document_authenticity',
      weight: 10,
      minimum_score: 70,
      is_mandatory: false,
      scoring_rules: {},
      order: rubric.criteria.length,
    };
    setRubric((prev) => ({ ...prev, criteria: [...prev.criteria, newCriterion] }));
  }, [rubric.criteria.length]);

  const updateCriterion = useCallback((id: number, field: keyof RubricCriteria, value: any) => {
    setRubric((prev) => ({
      ...prev,
      criteria: prev.criteria.map((c) =>
        c.id === id ? { ...c, [field]: value } : c
      ),
    }));
  }, []);

  const removeCriterion = useCallback((id: number) => {
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
          order: index,
        }));
        return { ...prev, criteria: updatedCriteria };
      });
    }
  }, []);

  const validateWeights = useCallback(() => {
    const totalWeight = rubric.criteria.reduce((sum, c) => sum + (c.weight || 0), 0);
    if (totalWeight !== 100) {
      setErrors({ weights: `Total weight must be 100% (current: ${totalWeight}%)` });
      return false;
    }
    setErrors({});
    return true;
  }, [rubric.criteria]);

  const saveRubric = useCallback(async () => {
    if (!validateWeights()) return;

    setSaving(true);
    try {
      const newRubric = await dispatch(createRubric(rubric)).unwrap();
      toast.success('Rubric saved successfully!');
      navigate(`/rubrics/${newRubric.id}`);
    } catch (error: any) {
      toast.error(error.message || 'Failed to save rubric');
    } finally {
      setSaving(false);
    }
  }, [rubric, validateWeights, dispatch, navigate]);

  const weightValid = rubric.criteria.reduce((sum, c) => sum + (c.weight || 0), 0) === 100;
  const criteriaIds = useMemo(() => rubric.criteria.map((c) => c.id), [rubric.criteria]);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-6">
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h1 className="text-3xl font-bold mb-6">Create New Rubric</h1>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div>
              <label htmlFor="rubric-name" className="block text-sm font-medium text-slate-800 mb-2">Name *</label>
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
              <p className="block text-sm font-medium text-slate-800 mb-2">Type *</p>
              <Select value={rubric.rubric_type} onValueChange={(value) => setRubric({ ...rubric, rubric_type: value as ApplicationType })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Rubric Types</SelectLabel>
                    {criteriaTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label htmlFor="rubric-passing-score" className="block text-sm font-medium text-slate-800 mb-2">Passing Score (%)*</label>
              <Input
                id="rubric-passing-score"
                type="number"
                value={rubric.passing_score}
                onChange={(e) => setRubric({ ...rubric, passing_score: parseInt(e.target.value) })}
                min="0"
                max="100"
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label htmlFor="rubric-department" className="block text-sm font-medium text-slate-800 mb-2">Department</label>
              <input
                id="rubric-department"
                type="text"
                value={rubric.department}
                onChange={(e) => setRubric({ ...rubric, department: e.target.value })}
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Optional department"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <textarea
              value={rubric.description}
              onChange={(e) => setRubric({ ...rubric, description: e.target.value })}
              placeholder="Rubric description (optional)"
              rows={4}
              className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            
            <div>
              <label htmlFor="rubric-position-level" className="block text-sm font-medium text-slate-800 mb-2">Position Level</label>
              <input
                id="rubric-position-level"
                type="text"
                value={rubric.position_level}
                onChange={(e) => setRubric({ ...rubric, position_level: e.target.value })}
                className="w-full px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Optional position level"
              />
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">Criteria ({rubric.criteria.length})</h2>
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
                Save Rubric
              </>
            )}
          </button>
        </div>
        
        {errors.weights && (
          <div className="mt-4 p-4 bg-amber-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertCircle className="w-5 h-5" />
              <span>{errors.weights}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

