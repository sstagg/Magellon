import {Routes, Route, Navigate,} from "react-router-dom";
import {MainWebTemplate} from "./components/templates/web/MainWebTemplate.tsx";
import {PanelTemplate} from "./components/templates/panel/PanelTemplate.tsx";
import {PageNotFoundView} from "./components/views/PageNotFoundView.tsx";

// const Account = Loadable({
//     loader: () => import(/* webpackChunkName: "account" */ 'app/modules/account'),
//     loading: () => <div>loading ...</div>,
// });
//
// const Admin = Loadable({
//     loader: () => import(/* webpackChunkName: "administration" */ 'app/modules/administration'),
//     loading: () => <div>loading ...</div>,
// });

const AppRoutes = () => {

    // const mainRoutes = {
    //     path: '/',
    //     element: <MainWebTemplate />,
    //     children: [
    //         {path: '*', element: <Navigate to='/404' />},
    //         {path: '/', element: <MainWebTemplate />},
    //         {path: '404', element: <PageNotFoundView />},
    //         {path: 'account', element: <Navigate to='/account/list' />},
    //     ],
    // };
    //
    // const accountRoutes = {
    //     path: 'account',
    //     element: <AccountLayout />,
    //     children: [
    //         {path: '*', element: <Navigate to='/404' />},
    //         {path: ':id', element: <AccountDetailView />},
    //         {path: 'add', element: <AccountAddView />},
    //         {path: 'list', element: <AccountListView />},
    //     ],
    // };
    //
    // const routing = useRoutes([mainRoutes, accountRoutes]);
    // return <>{routing}</>;
    return (
        <Routes>
            {/*<Route path="/" element={<Home/>}/>*/}
            <Route path="/" element={<Navigate to='/en/web'/>}/>
            <Route path="*" element={<Navigate to='/404'/>}/>
            <Route path="404" element={<PageNotFoundView/>}/>
            <Route path="/:lang/web/*" element={<MainWebTemplate/>}/>
            <Route path="/:lang/panel/*" element={<PanelTemplate/>}/>
        </Routes>
    );


};

export default AppRoutes;