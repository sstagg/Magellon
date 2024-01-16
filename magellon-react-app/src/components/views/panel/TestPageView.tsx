import {Grid} from "@mui/material";
import Container from "@mui/material/Container";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import {useState} from "react";

interface Image {
    id: number;
    name: string;
    parentId: number | null;
    price: number;
}

const images: Image[] = [{"id":1,"name":"Image 1","parentId":null,"price":10},{"id":2,"name":"Image 2","parentId":null,"price":20},{"id":3,"name":"Image 3","parentId":null,"price":30},{"id":4,"name":"Image 4","parentId":null,"price":40},{"id":5,"name":"Image 5","parentId":null,"price":50},{"id":6,"name":"Image 6","parentId":null,"price":60},{"id":7,"name":"Image 7","parentId":null,"price":70},{"id":8,"name":"Image 8","parentId":null,"price":80},{"id":9,"name":"Image 9","parentId":null,"price":90},{"id":10,"name":"Image 10","parentId":null,"price":100},{"id":11,"name":"Image 11","parentId":null,"price":110},{"id":12,"name":"Image 12","parentId":null,"price":120},{"id":13,"name":"Image 13","parentId":null,"price":130},{"id":14,"name":"Image 14","parentId":null,"price":140},{"id":15,"name":"Image 15","parentId":null,"price":150},{"id":16,"name":"Image 16","parentId":null,"price":160},{"id":17,"name":"Image 17","parentId":null,"price":170},{"id":18,"name":"Image 18","parentId":null,"price":180},{"id":19,"name":"Image 19","parentId":null,"price":190},{"id":20,"name":"Image 20","parentId":null,"price":200},{"id":21,"name":"Image 21","parentId":1,"price":210},{"id":22,"name":"Image 22","parentId":2,"price":220},{"id":23,"name":"Image 23","parentId":3,"price":230},{"id":24,"name":"Image 24","parentId":4,"price":240},{"id":25,"name":"Image 25","parentId":5,"price":250},{"id":26,"name":"Image 26","parentId":6,"price":260},{"id":27,"name":"Image 27","parentId":7,"price":270},{"id":28,"name":"Image 28","parentId":8,"price":280},{"id":29,"name":"Image 29","parentId":9,"price":290},{"id":30,"name":"Image 30","parentId":10,"price":300},{"id":31,"name":"Image 31","parentId":11,"price":310},{"id":32,"name":"Image 32","parentId":12,"price":320},{"id":33,"name":"Image 33","parentId":13,"price":330},{"id":34,"name":"Image 34","parentId":14,"price":340},{"id":35,"name":"Image 35","parentId":15,"price":350},{"id":36,"name":"Image 36","parentId":16,"price":360},{"id":37,"name":"Image 37","parentId":17,"price":370},{"id":38,"name":"Image 38","parentId":18,"price":380},{"id":39,"name":"Image 39","parentId":19,"price":390},{"id":40,"name":"Image 40","parentId":20,"price":400},{"id":41,"name":"Image 41","parentId":21,"price":410},{"id":42,"name":"Image 42","parentId":22,"price":420},{"id":43,"name":"Image 43","parentId":23,"price":430},{"id":44,"name":"Image 44","parentId":24,"price":440},{"id":45,"name":"Image 45","parentId":25,"price":450},{"id":46,"name":"Image 46","parentId":26,"price":460},{"id":47,"name":"Image 47","parentId":27,"price":470},{"id":48,"name":"Image 48","parentId":28,"price":480},{"id":49,"name":"Image 49","parentId":29,"price":490},{"id":50,"name":"Image 50","parentId":30,"price":500},{"id":51,"name":"Image 51","parentId":31,"price":510},{"id":52,"name":"Image 52","parentId":32,"price":520},{"id":53,"name":"Image 53","parentId":33,"price":530},{"id":54,"name":"Image 54","parentId":34,"price":540},{"id":55,"name":"Image 55","parentId":35,"price":550},{"id":56,"name":"Image 56","parentId":36,"price":560},{"id":57,"name":"Image 57","parentId":37,"price":570},{"id":58,"name":"Image 58","parentId":38,"price":580},{"id":59,"name":"Image 59","parentId":39,"price":590},{"id":60,"name":"Image 60","parentId":40,"price":600},{"id":61,"name":"Image 61","parentId":11,"price":610},{"id":62,"name":"Image 62","parentId":12,"price":620},{"id":63,"name":"Image 63","parentId":13,"price":630},{"id":64,"name":"Image 64","parentId":14,"price":640},{"id":65,"name":"Image 65","parentId":15,"price":650},{"id":66,"name":"Image 66","parentId":16,"price":660},{"id":67,"name":"Image 67","parentId":17,"price":670},{"id":68,"name":"Image 68","parentId":18,"price":680},{"id":69,"name":"Image 69","parentId":19,"price":690},{"id":70,"name":"Image 70","parentId":20,"price":700},{"id":71,"name":"Image 71","parentId":21,"price":710},{"id":72,"name":"Image 72","parentId":22,"price":720},{"id":73,"name":"Image 73","parentId":23,"price":730},{"id":74,"name":"Image 74","parentId":24,"price":740},{"id":75,"name":"Image 75","parentId":25,"price":750},{"id":76,"name":"Image 76","parentId":26,"price":760},{"id":77,"name":"Image 77","parentId":27,"price":770},{"id":78,"name":"Image 78","parentId":28,"price":780},{"id":79,"name":"Image 79","parentId":29,"price":790},{"id":80,"name":"Image 80","parentId":30,"price":800},{"id":81,"name":"Image 79","parentId":71,"price":790},{"id":82,"name":"Image 80","parentId":71,"price":800}];


function ImageTable({ data, onRowClick }: { data: Image[], onRowClick: (image: Image) => void}) {
    return (
        <Table>
            <TableHead>
                <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Parent</TableCell>
                </TableRow>
            </TableHead>
            <TableBody>
                {data.map((image, index) => (
                        <TableRow onClick={() => onRowClick(image)} key={image.id}>
                            <TableCell>{image.id}</TableCell>
                            <TableCell >{image.name}</TableCell>
                            <TableCell>{image.parentId}</TableCell>
                        </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}



interface ImageGridProps {
    selectedImages: (Image | null)[];
    onRowClick: (image: Image, column: number) => void;
    getColumnData: (column: number) => Image[];
}
const ImageGrid: React.FC<ImageGridProps> = ({ selectedImages, onRowClick, getColumnData }) => {
    return (
        <Container style={{ width: '100vw' }}>
            <h1>Hello</h1>
            <Grid container direction="row">
                {selectedImages.map((_, index) => (
                    <Grid item xs={3} key={index}>
                        <h1>Column {index}</h1>
                        <ImageTable data={getColumnData(index)} onRowClick={(image) => onRowClick(image, index)} />
                    </Grid>
                ))}
            </Grid>
        </Container>
    );
};


// const [selectedImageGr, setSelectedImageGr] = useState<Image | null>(null);
// const [selectedImageSq, setSelectedImageSq] = useState<Image | null>(null);
export const TestPageView = () => {
    const [selectedImages, setSelectedImages] = useState<(Image | null)[]>([null, null, null,null]);

    const handleRowClick = (image: Image, column: number) => {
        if(column === selectedImages.length) {return;}// this is last column , when an image is selected, nothing needs to be done
        const updatedImages = selectedImages.map((selectedImage, index) => (
            index === column ? image : (index > column ? null : selectedImage)
        ));
        // updatedImages.push(null);
        setSelectedImages(updatedImages);
    };

    const getColumnData = (column: number): Image[] => {
        const parentId = column === 0 ? null : selectedImages[column - 1]?.id;
        return parentId !== undefined ? getChildrenByParentId(parentId) : [];
    };

    function getChildrenByParentId( parentId: number | null): Image[] {
        return images.filter((image) => image.parentId === parentId);
    }


    return (

        <ImageGrid
            selectedImages={selectedImages}
            onRowClick={handleRowClick}
            getColumnData={getColumnData}
        />

        // <Container style={{ width: '100vw' }}>
        //     <h1>Hello</h1>
        //     <Grid container direction="row">
        //         <Grid item xs={3}>
        //             <h1>gr</h1>
        //             <ImageTable data={getColumnData( 0)} onRowClick={(image) => handleRowClick(image, 0)} />
        //         </Grid>
        //         <Grid item xs={3}>
        //             <h1>sq</h1>
        //             <ImageTable data={getColumnData(1)} onRowClick={(image) => handleRowClick(image, 1)} />
        //         </Grid>
        //         <Grid item xs={3}>
        //             <h1>hl</h1>
        //             <ImageTable data={getColumnData(2)}  onRowClick={(image) => handleRowClick(image, 2)} />
        //         </Grid>
        //         <Grid item xs={3}>
        //             <h1>hl</h1>
        //             <ImageTable data={getColumnData(3)}  onRowClick={(image) => handleRowClick(image, 3)} />
        //         </Grid>
        //     </Grid>
        // </Container>
    );
};