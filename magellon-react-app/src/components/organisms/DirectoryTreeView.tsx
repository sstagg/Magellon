import React, { useEffect, useState } from "react";
import axios from "axios";
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';

type TreeNode = {
    id: string;
    label: string;
    path: string;
    children?: TreeNode[] | null;
};

const DirectoryTreeView: React.FC = () => {
    const [treeData, setTreeData] = useState<TreeNode[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await axios.get<TreeNode[]>("http://localhost:8000/web/directory-tree?root_path=fgb");
                if (response.headers['content-type']?.includes('application/json')) {
                    setTreeData(response.data);
                } else {
                    console.error("The response is not JSON:", response.data);
                }
            } catch (error) {
                console.error("Error fetching data:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    const renderTree = (nodes: TreeNode[]) => {
        return nodes.map(node => (
            node.children && node.children.length > 0 ? (
                <TreeItem
                    key={node.id}
                    itemId={node.id}
                    label={node.label}
                >
                    {renderTree(node.children)}
                </TreeItem>
            ) : (
                <TreeItem key={node.id} itemId={node.id} label={node.label} />
            )
        ));
    };


    if (loading) {
        return <p>Loading...</p>;
    }

    return (
        <SimpleTreeView>
            {/* Render only the children of the root nodes */}
            {treeData.flatMap(rootNode =>
                rootNode.children ? renderTree(rootNode.children) : []
            )}
        </SimpleTreeView>
    );
};

export default DirectoryTreeView;