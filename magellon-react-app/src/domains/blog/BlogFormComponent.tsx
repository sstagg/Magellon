import React, {useEffect, useState} from 'react'
import Container from "@mui/material/Container";
import {
    Button, Checkbox,
    FormControl,
    FormControlLabel,
    FormGroup,
    FormLabel,
    Grid,
    MenuItem,
    Select,
    TextField,
    Typography
} from "@mui/material";
import { IBlog} from "./Blog.Model.ts";
import {useForm} from "react-hook-form";
import {Link, useNavigate, useParams} from "react-router-dom";
import {useTranslation} from "react-i18next";
import {
    useCreateBlogMutation,
    useGetSoloBlogQuery,
    useLazyGetSoloBlogQuery,
    useUpdateBlogMutation
} from './BlogRtkRestApi.ts';
import EmptyState from "../../core/EmptyState.tsx";




export default function BlogFormComponent() {
    const {lang,id} = useParams(); // Assuming you're using React Router to get the blogId from the URL

    //console.log("BlogFormComponent");
    // const dispatch = useDispatch();

    const navigate = useNavigate();
    // const { t, i18n } = useTranslation('blog');
    const { t, i18n } = useTranslation(['blog', 'global']);

    const [updateBlog , {isLoading:isUpdateBlogLoading}] = useUpdateBlogMutation();
    const [createBlog, { isLoading:isCreateBlogLoading }] = useCreateBlogMutation();
    const {handleSubmit, register,setError,setValue, formState: {errors, isValid}} = useForm<IBlog>({
        mode: 'onChange',
    });
     const isEditing = (id ?? 0 > 0);
    //const [triger ,result } = useLazyGetSoloBlogQuery(id);
    const { data: queryData, isLoading: queryIsLoading, isError: queryIsError } = useGetSoloBlogQuery(id,{skip:!id});

    useEffect(() => {

            // Call useGetSoloBlogQuery only when in editing mode
            if ( isEditing && !queryIsLoading  && !queryIsError) {
                // Set form field values when theSelectedBlog is available
                setValue('id', queryData?.id);
                setValue('title', queryData?.title);
                setValue('body', queryData?.body);
            }
    }, [ queryData, queryIsLoading, queryIsError]);


    const OnFormSubmit = (data) => {

       //  setError("title", {
       //      type: 'server',
       //      message: "name is very good",
       //  });

        try {
            const blog:IBlog = {
                // id: data.id, // Include ID for updates (assuming it's available in your form data)
                id: isEditing ? data.id : null, // Include ID for updates (assuming it's available in your form data)
                title: data.title,
                body: data.body,
            };

            if(!isEditing) {
                createBlog(blog).
                unwrap().
                then((createdData) => {
                    console.log('Blog post created:', createdData);}
                    //navigate('/'); // Redirect to the blog list or the updated blog's page
                ).catch((error) => {
                    // Handle the update error, display an error message, or handle as needed
                    console.error('Error creating blog:', error);
                });

            }else{
                updateBlog(blog).
                unwrap().
                then((updatedData) => {
                        console.log('Blog post updated:', updatedData);}
                    //navigate('/'); // Redirect to the blog list or the updated blog's page
                ).catch((error) => {
                    // Handle the update error, display an error message, or handle as needed
                    console.error('Error updating blog:', error);
                });
            }

        } catch (error) {
            // Handle the update error, display an error message, or handle as needed
            console.error('Error updating blog:', error);
        }

    };
    const isBodyValid = async (body) => {
        try {
            console.log("body validation is called")
            //const response = await axios.get(`/api/check-email?email=${email}`); // Replace with your API endpoint
            return  true;
        } catch (error) {
            console.error(error);
            return false;
        }
    };

    if (isEditing && (queryIsLoading||queryIsError|| !queryData)) {
        return (<EmptyState isLoading={queryIsLoading} isError={queryIsError} data={queryData} errorMessage={t('error.loadingError',{ns:'global', entity: 'Blogs'  })}/>)
    }

    return (
        <Container>
            <form onSubmit={handleSubmit(OnFormSubmit)}>


                <Grid container rowSpacing={1} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                    <Grid item xs={12}  >
                        <Typography variant="h4">{t('blog.name',{ ns: 'blog' })}</Typography>
                        <Typography>Please fill in the details below:</Typography>
                        {/*<Typography>{t('blog.message2',{ns:'blog', name: 'Behdad' ,count:5 })}</Typography>*/}
                        {/*<Typography>{t('blog.message3',{ns:'blog', gender: 'male' })}</Typography>*/}
                        {/*<Typography>{i18n.t('blog.plural',{ns:'blog', n: 2 })}</Typography>*/}
                        {/*<Typography>{i18next.t('blog.price',{ns:'blog',val:2000 })}</Typography>*/}
                    </Grid>

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            <FormLabel>{t('blog.columns.id',{ ns: 'blog' })}</FormLabel>
                            <TextField
                                label={t('blog.columns.id',{ ns: 'blog' })}
                                variant="filled"
                                disabled
                                margin="dense"
                                {...register('id')}
                                error={!!errors.id}
                                helperText={errors.id ? 'Id is required' : ''}
                            />
                        </FormControl>
                    </Grid>
                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            <FormLabel>{t('blog.columns.title',{ ns: 'blog' })}</FormLabel>
                            <TextField
                                label={t('blog.columns.title',{ ns: 'blog' })}
                                variant="filled"
                                margin="dense"
                                {...register('title')}
                                error={!!errors.title}
                                helperText={!!errors.title }
                            />
                        </FormControl>
                    </Grid>

                    <Grid item xs={8}>
                        <FormControl fullWidth>
                            <FormLabel>Body</FormLabel>
                            <TextField
                                label="Body"
                                variant="filled"
                                multiline
                                margin="dense"
                                rows={5}
                                {...register('body', {
                                    required: 'Body is required',
                                    // validate: async (value) => {
                                    //     if (!value) return true; // Skip validation if empty
                                    //     const isValid = await isBodyValid(value);
                                    //     if (!isValid) {
                                    //         return 'This body is not valid';
                                    //     }
                                    //     return true;
                                    // },
                                })}
                                error={!!errors.body}
                                helperText={errors.body ? errors.body.message : ''}
                            />
                        </FormControl>
                    </Grid>


                    <Grid item xs={6}>
                        <Button variant="contained" color="primary" type="submit"> {t('entity.action.save', { ns: 'global' })} </Button>
                        <Link to={-1}>  {t('entity.action.back', { ns: 'global' })}</Link>
                        {/*<Button variant="contained" color="secondary"  onClick={()=> navigate(-1)}> Back </Button>*/}
                    </Grid>

                </Grid>

            </form>

        </Container>
    )
}
