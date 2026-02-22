// src/hooks/useProfile.ts (Renamed & Tweaked)
import { useQuery } from '@tanstack/react-query';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/app/store';
import { fetchProfile } from '@/store/authSlice';
import { authService } from '@/services/auth.service';
// import { toast } from 'react-toastify';

export function useProfile() {
  const dispatch = useDispatch<AppDispatch>();

  return useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const res = await authService.getProfile();  // Use service
      dispatch(fetchProfile());  // Sync to Redux (optional, if thunk calls same)
      return res.user;  // Return just user (or full { user, user_type })
    },
    staleTime: 1000 * 60 * 5,  // 5 min
    retry: 1,
    
    enabled: true,  // Or tie to isAuthenticated
  });
}