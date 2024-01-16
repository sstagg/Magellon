import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import {settings} from "../../core/settings.ts";
import {IBlog} from "./Blog.Model.ts";


export const blogRtkRestApi = createApi({
    baseQuery: fetchBaseQuery({ baseUrl: settings.apiBaseUrl }), // Set your API base URL here
    tagTypes: ['blogs'],

    endpoints: (builder) => ({
        getPagedBlogs: builder.query<{ data: IBlog[]; totalPages: number }, { page: number; pageSize: number }>({
            query: ({ page, pageSize }) => `${settings.api_endpoints.blogs}?page=${page}&pageSize=${pageSize}`,
        }),
        getBlogs: builder.query<IBlog[], void>({
            query: () => settings.api_endpoints.blogs, // Define your endpoint for fetching blogs
        }),
        getSoloBlog: builder.query<IBlog, number>({
            query: (id: number) => `${settings.api_endpoints.blogs}/${id}`, // Define your endpoint for fetching a single blog by ID
        }),

        createBlog: builder.mutation<IBlog, IBlog>({
            query: (newBlog) => ({
                url: settings.api_endpoints.blogs,
                method: 'POST',
                body: newBlog,
            }),
            invalidatesTags:['blogs'],
        }),

        updateBlog: builder.mutation<IBlog, IBlog>({
            query: (updatedBlog) => ({
                url: `${settings.api_endpoints.blogs}/${updatedBlog.id}`,
                method: 'PUT',
                body: updatedBlog,
            }),
            invalidatesTags:['blogs'],
        }),

        deleteBlog: builder.mutation({
            query: (blogId) => ({
                url: `${settings.api_endpoints.blogs}/${blogId}`,
                method: 'DELETE',
            }),
            invalidatesTags:['blogs'],
        }),


    }),
});

export const { useGetBlogsQuery,useGetSoloBlogQuery,useLazyGetSoloBlogQuery,useGetPagedBlogsQuery, useCreateBlogMutation, useUpdateBlogMutation, useDeleteBlogMutation } = blogRtkRestApi;
