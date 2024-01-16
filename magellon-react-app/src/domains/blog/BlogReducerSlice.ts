import axios, {AxiosError} from 'axios';

import {defaultValue, IBlog} from './Blog.Model';
import {createAsyncThunk, createSlice} from "@reduxjs/toolkit";
import {IReduxState} from "../../core/IReduxState.ts";
import {settings} from "../../core/settings.ts";
import getAxiosClient from "../../core/AxiosClient.ts";

const initialState: IReduxState<IBlog> = {
    loading: false,
    updating: false,
    updateState: false,
    response: null,
    error: null,
    entity: defaultValue,
    entities: [] as ReadonlyArray<IBlog>,
    currentPage: 1,
    numberOfPages: 0,
};


const AxiosClient = getAxiosClient(settings.apiBaseUrl);

export const fetchBlogs = createAsyncThunk(
    "blog/fetchBlogs",
    async (_, {rejectWithValue}) => {
        try {
            const theAxiosResponse = await AxiosClient.get(`${settings.api_endpoints.blogs}?cacheBuster=${new Date().getTime()}`);
            return theAxiosResponse.data;
        } catch (err: any) {
            if (err instanceof AxiosError) {
                return rejectWithValue(err.message);
            } else {
                return rejectWithValue('An error occurred');
            }
        }
    }
);


export const createBlog = createAsyncThunk(
    "blog/createBlog",
    async (data: IBlog, {rejectWithValue}) => {
        try {
            const theAxiosResponse = await axios.post(`${settings.api_endpoints.blogs}`, data);
            return theAxiosResponse.data;
        } catch (err) {
            return rejectWithValue(err.message);
        }


    }
);

export const updateBlog = createAsyncThunk(
    "blog/updateBlog",
    async (data: IBlog) => {
        try {
            const theAxiosResponse = await axios.post(`${settings.api_endpoints.blogs}`, data);
            return theAxiosResponse.data;
        } catch (err) {
            //return rejectWithValue(err.response.data);
        }


    }
);
export const deleteBlog = createAsyncThunk(
    "blog/removeBlog",
    async (data: IBlog) => {
        try {
            const theAxiosResponse = await axios.post(`${settings.api_endpoints.blogs}`, data);
            return theAxiosResponse.data;
        } catch (err) {
            //return rejectWithValue(err.response.data);
        }


    }
);


// export const createTour = createAsyncThunk(
//     "blog/createBlog",
//     async ({ updatedTourData, navigate, toast }, { rejectWithValue }) => {
//         try {
//             const response = await API.post("/tour", updatedTourData);
//             toast.success("Added Successfully");
//             navigate("/dashboard");
//             return response.data;
//         } catch (err) {
//             return rejectWithValue(err.response.data);
//         }
//     }
// );

export const BlogReducerSlice = createSlice({
    name: 'blogSlice',
    initialState,
    reducers: {
        changeStateTrue: (state) => {
            state.updateState = true;
        },
        changeStateFalse: (state) => {
            state.updateState = false;
        },
        clearResponse: (state) => {
            state.response = "";
        },
    },

    extraReducers: {

        [createBlog.pending]: (state) => {
            state.loading = true;
        },
        [createBlog.fulfilled]: (state, action) => {
            state.loading = false;
            state.entities.push(action.payload);
            state.response = "add";
        },
        [createBlog.rejected]: (state, action) => {
            state.loading = false;
            state.error = action.payload.error;
        },



        [fetchBlogs.pending]: (state, action) => {
            state.entities = action.payload;
            // console.log("Blogs Fetching");
        },
        [fetchBlogs.fulfilled]: (state, action) => {
            state.loading = false;
            state.entities =action.payload;
            // console.log("Blogs fullfilled");
        },
        [fetchBlogs.rejected]: (state, action) => {
            state.loading = false;
            state.error = action.payload;
            // console.log("Blogs rejected");
        },


        [updateBlog.pending]: (state) => {
            state.loading = true;
        },
        [updateBlog.fulfilled]: (state, action) => {
            const updateItem = action.payload;
            console.log(updateItem);
            const index = state.entities.findIndex((item) => item.id === updateItem.id);
            if (index !== -1) {
                state.entities[index] = updateItem;
            }
            state.response = "update";
        },
        [updateBlog.rejected]: (state, action) => {
            state.loading = false;
            state.error = action.payload.error;
        },


        [deleteBlog.pending]: (state) => {
            state.loading = true;
        },
        [deleteBlog.fulfilled]: (state, action) => {
            state.entities = state.entities.filter((item) => item.id !== action.payload);
            state.response = "delete";
        },
        [deleteBlog.rejected]: (state, action) => {
            state.loading = false;
            state.error = action.payload.error;
        },

    },


})


// Action creators are generated for each case reducer function
export const {changeStateTrue, changeStateFalse, clearResponse} = BlogReducerSlice.actions

export default BlogReducerSlice.reducer