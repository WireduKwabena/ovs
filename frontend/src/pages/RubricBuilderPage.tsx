// src/pages/RubricBuilderPage.tsx
import React from 'react';
// import { useParams } from 'react-router-dom';
import { Navbar } from '@/components/common/Navbar';
import { RubricBuilder } from '@/components/rubrics/RubricBuilder';

export const RubricBuilderPage: React.FC = () => {
  // const { rubricId } = useParams<{ rubricId?: string }>();

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <RubricBuilder  />
      </div>
    </div>
  );
};

export default RubricBuilderPage;



