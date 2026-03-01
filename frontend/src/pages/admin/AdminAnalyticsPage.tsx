import React from 'react';

import { Analytics } from '@/components/admin/Analytics';
import { AnalyticsDashboard } from '@/components/admin/AnalyticsDashboard';

const AdminAnalyticsPage: React.FC = () => {
  return (
    <div className="space-y-10">
      <Analytics />
      <AnalyticsDashboard />
    </div>
  );
};

export default AdminAnalyticsPage;
