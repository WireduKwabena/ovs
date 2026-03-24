// src/store/store.ts (Tweaked)
import { configureStore, combineReducers, type Action } from '@reduxjs/toolkit';
import {  persistStore, persistReducer, FLUSH,REHYDRATE,PAUSE,PERSIST,PURGE,REGISTER, } from 'redux-persist';
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

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['auth'], // Persist only auth (avoids bloat)
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