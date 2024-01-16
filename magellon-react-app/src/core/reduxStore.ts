import { configureStore } from '@reduxjs/toolkit'
import counterReducer from '../domains/counter/counterSlice.ts'
import BlogReducerSlice from "../domains/blog/BlogReducerSlice.ts";
import {blogRtkRestApi} from "../domains/blog/BlogRtkRestApi.ts";
export const store = configureStore({
    reducer: {
        counter: counterReducer,
        blogsKey: BlogReducerSlice,
        [blogRtkRestApi.reducerPath]: blogRtkRestApi.reducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(blogRtkRestApi.middleware),
});
// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof store.dispatch