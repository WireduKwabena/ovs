// src/components/rubrics/CriteriaCard.tsx
import { XCircle } from 'lucide-react';
import type { RubricCriteria } from '@/types';
import { Input } from '../ui/input';
import { Button } from '../ui/button';

interface CriteriaCardProps {
  criterion: RubricCriteria;
  onUpdate: (field: string, value: any) => void;
  onDelete: () => void;
}

export function CriteriaCard({ criterion, onUpdate, onDelete }: CriteriaCardProps) {
  

  return (
    <div className="bg-white rounded-lg shadow-md p-6 border-l-4 border-blue-500">
      <div className="flex justify-between items-start mb-4">
        <h4 className="text-lg font-semibold text-gray-900">{criterion.name}</h4>
        <Button onClick={onDelete} className="text-red-500 hover:text-red-700">
          <XCircle className="w-5 h-5" />
        </Button>
      </div>
      
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Type</span>
          <span className="text-sm text-gray-900">{criterion.criteria_type}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <label htmlFor={`criterion-weight-${criterion.id}`} className="text-sm font-medium text-gray-700">Weight</label>
          <Input
            id={`criterion-weight-${criterion.id}`}
            type="number"
            value={criterion.weight}
            onChange={(e) => onUpdate('weight', parseInt(e.target.value))}
            className="w-20 px-2 py-1 border rounded text-sm"
            min="0"
            max="100"
          />
        </div>
        
        <div className="flex items-center justify-between">
          <label htmlFor={`criterion-min-score-${criterion.id}`} className="text-sm font-medium text-gray-700">Min Score</label>
          <Input
            id={`criterion-min-score-${criterion.id}`}
            type="number"
            value={criterion.minimum_score}
            onChange={(e) => onUpdate('minimum_score', parseInt(e.target.value))}
            className="w-20 px-2 py-1 border rounded text-sm"
            min="0"
            max="100"
          />
        </div>
        
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={criterion.is_mandatory}
            onChange={(e) => onUpdate('is_mandatory', e.target.checked)}
            className="w-5 h-5 text-blue-600 rounded"
          />
          <span className="text-sm font-medium text-gray-700">Mandatory</span>
        </label>
      </div>
      
      {criterion.scoring_rules && Object.keys(criterion.scoring_rules).length > 0 && (
        <div className="mt-4 p-3 bg-gray-50 rounded">
          <h5 className="text-sm font-semibold mb-2">Scoring Rules</h5>
          <pre className="text-xs text-gray-600 overflow-auto max-h-32">{JSON.stringify(criterion.scoring_rules, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
