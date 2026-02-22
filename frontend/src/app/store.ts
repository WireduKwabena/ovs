// src/store/store.ts (Tweaked)
import { configureStore, combineReducers } from '@reduxjs/toolkit';
import {  persistStore, persistReducer, FLUSH,REHYDRATE,PAUSE,PERSIST,PURGE,REGISTER, } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import authReducer from '@/store/authSlice';  // Absolute or relative fix
import applicationReducer from '@/store/applicationSlice';
import notificationReducer from '@/store/notificationSlice';
import rubricReducer from '@/store/rubricSlice';
import errorReducer from '@/store/errorSlice';
import interviewReducer from '@/store/interviewSlice'; 


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
  // [applicationsApi.reducerPath]: applicationsApi.reducer,  // Future: Add RTK Query
});

const persistedReducer = persistReducer(persistConfig, rootReducer);

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