// src/store/store.ts (Tweaked)
import { configureStore, combineReducers, type Action } from '@reduxjs/toolkit';
import { persistStore, persistReducer, createTransform, FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import authReducer from '@/store/authSlice';  // Absolute or relative fix
import applicationReducer from '@/store/applicationSlice';
import notificationReducer from '@/store/notificationSlice';
import rubricReducer from '@/store/rubricSlice';
import errorReducer from '@/store/errorSlice';
import interviewReducer from '@/store/interviewSlice';

/**
 * Action type dispatched by the logout thunk to wipe all non-auth slices from
 * memory, preventing data from a previous user session being visible to a
 * subsequent user who logs in without a full page reload.
 */
export const STORE_RESET = 'store/reset' as const;

/**
 * Strip security-sensitive fields before writing auth state to localStorage.
 * JWT tokens (access + refresh) must never be stored in localStorage because
 * any XSS payload on the page can read localStorage and exfiltrate them.
 * Non-sensitive context (user profile, org memberships, roles) is preserved so
 * the UI can render correctly while a silent re-auth is attempted on page load.
 * `isAuthenticated` is also cleared so the app always verifies the session on
 * rehydration rather than trusting stale storage state.
 */
const authStorageTransform = createTransform(
  // outbound: what gets written to localStorage
  (state: Record<string, unknown>) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { tokens, isAuthenticated, loading, switchingActiveOrganization, silentRefreshPending, ...safeState } = state;
    return safeState;
  },
  // inbound: what the store receives when rehydrating from localStorage
  (state: Record<string, unknown>) => ({
    ...state,
    tokens: null,
    isAuthenticated: false,
    loading: false,
    switchingActiveOrganization: false,
    silentRefreshPending: false,
  }),
  { whitelist: ['auth'] },
);

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['auth'],
  transforms: [authStorageTransform],
};

const rootReducer = combineReducers({
  auth: authReducer,
  applications: applicationReducer,
  notifications: notificationReducer,
  rubrics: rubricReducer,
  error: errorReducer,
  interview: interviewReducer,
});

type RootReducerState = ReturnType<typeof rootReducer>;

function resettableRootReducer(
  state: RootReducerState | undefined,
  action: Action,
): RootReducerState {
  if (action.type === STORE_RESET) {
    // Preserve auth (handled by authSlice's own clearSessionState) but wipe
    // every other slice so stale data from the previous user is never shown.
    return rootReducer(
      { auth: state?.auth } as RootReducerState,
      action,
    );
  }
  return rootReducer(state, action);
}

const persistedReducer = persistReducer(persistConfig, resettableRootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
      },
    }).concat(/* applicationsApi.middleware, // Future */),
});

export const persistor = persistStore(store);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;