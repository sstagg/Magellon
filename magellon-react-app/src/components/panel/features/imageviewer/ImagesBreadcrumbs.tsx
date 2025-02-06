import Link from "@mui/material/Link";
import {Breadcrumbs} from "@mui/material";

const parseName = (name : string | undefined | null) => {
    if (!name) {
        return [];
    }

    const parts = name.split('_');
    const breadcrumbs: React.ReactNode[] = [];

    let currentPath = '';
    parts.forEach((part, index) => {
        //const label = part.replace(/[0-9]+/g, ''); // Remove numeric characters
        const label = part; // Remove numeric characters
        const combinedLabel = currentPath ? `${currentPath}_${part}` : part;
        currentPath = combinedLabel;

        breadcrumbs.push(
            <Link key={index} underline="hover" color="inherit" href={`#${combinedLabel}`}>
                {label}
            </Link>
        );
    });

    return breadcrumbs;
};

export const ImagesBreadcrumbs: React.FC<{ name: string | undefined | null }> = ({ name }) => {

    const breadcrumbs = parseName(name);

    return (
        <Breadcrumbs aria-label="breadcrumb">
            {breadcrumbs}
        </Breadcrumbs>
    );
};