import React, {useEffect, useState} from 'react'
import {useGetBlogsQuery} from "./BlogRtkRestApi.ts";
import {IBlog} from "./Blog.Model.ts";
import {useDispatch, useSelector} from "react-redux";
import {fetchBlogs} from "./BlogReducerSlice.ts";
import {RootState} from "../../core/reduxStore.ts";
import {IReduxState} from "../../core/IReduxState.ts";
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import {createSvgIcon, TablePagination} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import {useNavigate} from "react-router-dom";
import {Dna} from "react-loader-spinner";

const PlusIcon = createSvgIcon(
    // credit: plus icon from https://heroicons.com/
    <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
    >
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>,
    'Plus',
);



export default function BlogTableComponent( ) {
    const { data, error,isFetching, isLoading } = useGetBlogsQuery();
    const [searchQuery, setSearchQuery] = useState('');
    const [page, setPage] = React.useState(0);
    const [rowsPerPage, setRowsPerPage] = React.useState(10);
    // const { data, error, isLoading } = useSearchBlogsQuery({ query: searchQuery });
    const navigate = useNavigate();

    const handleSearch = () => {
        // Trigger the search when the user clicks the search button or presses Enter
        // You can also debounce the search for better user experience
        // ...
    };

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(+event.target.value);
        setPage(0);
    };

    if (isLoading || isFetching) {
        return <div>
            <h3>Loading...</h3>
            <Dna
                visible={true}
                height="80"
                width="80"
                ariaLabel="dna-loading"
                wrapperStyle={{}}
                wrapperClass="dna-wrapper"
            />
        </div>;
    }

    if (error) {
        return <div>Error: {error}</div>;
    }

    function editBlog(blog : IBlog) {
        navigate(`${blog.id}/edit`);
    }

    return (
        <Paper sx={{ width: '100%', overflow: 'hidden' }}>
            <div>
                <input
                    type="text"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                            handleSearch();
                        }
                    }}
                />
                <button onClick={handleSearch}>Search</button>
                <IconButton aria-label="add" onClick={()=>navigate('new')}>
                    <PlusIcon  />
                </IconButton>
            </div>

            <TableContainer component={Paper} sx={{ maxHeight: 680 ,minWidth:480}}>
                <Table sx={{ minWidth: 650 }} stickyHeader aria-label="sticky  table">
                    <TableHead>
                        <TableRow>
                            <TableCell>ID</TableCell>
                            <TableCell align="right">Title</TableCell>

                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {data
                            .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                            .map((blog) => (
                              <TableRow
                                role="checkbox"
                                onClick={()=>editBlog(blog)}
                                hover
                                key={blog.id}
                                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                            >
                                <TableCell component="th" scope="row">
                                    {blog.id}
                                </TableCell>
                                <TableCell align="left">{blog.title}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
            <TablePagination
                rowsPerPageOptions={[10, 25, 100]}
                component="div"
                count={data.length}
                rowsPerPage={rowsPerPage}
                page={page}
                onPageChange={handleChangePage}
                onRowsPerPageChange={handleChangeRowsPerPage}
            />
        </Paper>
    );






    // const dispatch = useDispatch();
    // const result:IReduxState<IBlog> = useSelector( (state: RootState) => state.blogsKey    );
    // useEffect(() => {
    //     dispatch(fetchBlogs());
    // }, [dispatch]);
    // // console.log("BlogTableComponent");
    // // console.log('Result:', result);
    // return (
    //     <div>
    //         <h2>BlogTableComponent</h2>
    //         {result.loading && <p>Loading...</p>}
    //         {result.error && <p>Error: {result.error}</p>}
    //         {result.entities && (
    //             <ul>
    //                 {result.entities.map((blog) => (
    //                     <li key={blog.id}>{blog.title}</li>
    //                 ))}
    //             </ul>
    //         )}
    //     </div>
    // )
}
