import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Search,
  Plus,
  MoreVertical,
  Power,
  CreditCard,
  Filter,
  ArrowUpDown,
  Users
} from 'lucide-react';
import { toast } from 'react-toastify';
import { governanceService } from '@/services/governance.service';
import type { GovernancePlatformOrganizationOversight } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { getOrgAdminPath } from '@/utils/appPaths';

export const OrganizationRegistryPage: React.FC = () => {
  const navigate = useNavigate();
  const [organizations, setOrganizations] = useState<GovernancePlatformOrganizationOversight[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchOrganizations = useCallback(async () => {
    setLoading(true);
    try {
      const response = await governanceService.listPlatformOrganizations();
      setOrganizations(response.results);
    } catch {
      toast.error('Failed to load organization registry');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchOrganizations();
  }, [fetchOrganizations]);

  const handleToggleStatus = async (org: GovernancePlatformOrganizationOversight) => {
    setUpdatingId(org.id);
    try {
      const updated = await governanceService.updatePlatformOrganizationStatus(org.id, {
        is_active: !org.is_active
      });
      setOrganizations(prev => prev.map(o => o.id === org.id ? updated : o));
      toast.success(`${org.name} ${updated.is_active ? 'activated' : 'deactivated'}`);
    } catch {
      toast.error('Failed to update organization status');
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredOrgs = organizations.filter(org => 
    org.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    org.code.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-8">
      {/* Header section */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Organization Registry</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Provision, monitor, and manage the lifecycle of all platform organizations.
          </p>
        </div>
        <Button className="rounded-xl shadow-lg gap-2">
          <Plus className="h-4 w-4" />
          Provision New Organization
        </Button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Total Registered</p>
              <p className="text-2xl font-bold">{organizations.length}</p>
            </div>
          </div>
        </Card>
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
              <Power className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Active Units</p>
              <p className="text-2xl font-bold">{organizations.filter(o => o.is_active).length}</p>
            </div>
          </div>
        </Card>
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
              <CreditCard className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Premium Plans</p>
              <p className="text-2xl font-bold">{organizations.filter(o => o.subscription?.source === 'active').length}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Registry Filter/Search */}
      <Card className="p-4 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search organizations by name or code..." 
              className="w-full bg-background/50 border border-border/70 rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" className="rounded-xl gap-2 text-sm">
              <Filter className="h-4 w-4" />
              Filter
            </Button>
            <Button variant="outline" className="rounded-xl gap-2 text-sm">
              <ArrowUpDown className="h-4 w-4" />
              Sort
            </Button>
          </div>
        </div>
      </Card>

      {/* Registry Table/List */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : filteredOrgs.length === 0 ? (
          <Card className="p-12 text-center rounded-2xl border-dashed border-border/70 bg-muted/20">
            <p className="text-muted-foreground">No organizations found matching your search.</p>
          </Card>
        ) : (
          filteredOrgs.map(org => (
            <Card key={org.id} className="p-6 rounded-2xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="flex items-start gap-4">
                  <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                    <Building2 className="h-6 w-6 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-lg font-bold truncate">{org.name}</h3>
                      <Badge variant="outline" className="rounded-full font-bold uppercase tracking-widest text-[10px]">
                        {org.organization_type}
                      </Badge>
                      {org.is_active ? (
                        <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10 rounded-full border-emerald-500/20">Active</Badge>
                      ) : (
                        <Badge className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/10 rounded-full border-rose-500/20">Deactivated</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">Registry Code: <span className="font-mono font-medium text-foreground">{org.code}</span></p>
                    <div className="flex items-center gap-4 mt-3 text-[11px] font-bold uppercase tracking-[0.1em] text-muted-foreground">
                      <span className="flex items-center gap-1.5"><Users className="h-3.5 w-3.5" /> {org.active_member_count} Staff</span>
                      <span>{org.organization_type}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end md:self-center">
                  <div className="text-right mr-4 hidden xl:block">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Billing Posture</p>
                    <p className="text-sm font-semibold">{org.subscription?.plan_name || 'Free Tier'}</p>
                  </div>
                  <Button
                    variant="outline"
                    className="rounded-xl gap-2"
                    onClick={() => navigate(getOrgAdminPath(org.id, 'users'))}
                  >
                    <Users className="h-4 w-4" />
                    Registry Admins
                  </Button>
                  <Button 
                    variant={org.is_active ? "outline" : "default"} 
                    className="rounded-xl gap-2"
                    disabled={updatingId === org.id}
                    onClick={() => handleToggleStatus(org)}
                  >
                    <Power className="h-4 w-4" />
                    {updatingId === org.id ? 'Updating...' : org.is_active ? 'Deactivate' : 'Reactivate'}
                  </Button>
                  <Button variant="ghost" size="icon" className="rounded-xl">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default OrganizationRegistryPage;
