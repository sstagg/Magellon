/**
 * /panel/artifacts/:oid — workflow lineage viewer.
 *
 * Page wrapper around ``WorkflowChainView``. The bulk of the rendering
 * lives in the feature component; this page just plucks the OID from
 * the route, adds breadcrumbs, and keeps the layout consistent with
 * the rest of the panel.
 */
import React from 'react';
import { Container, Stack, Typography } from '@mui/material';
import { useParams } from 'react-router-dom';
import { WorkflowChainView } from '../../features/artifact-workflow/ui/WorkflowChainView.tsx';


export const ArtifactWorkflowPage: React.FC = () => {
    const { oid } = useParams<{ oid: string }>();

    if (!oid) {
        return (
            <Container maxWidth="md" sx={{ py: 3 }}>
                <Typography variant="h6">Artifact OID missing from the URL.</Typography>
            </Container>
        );
    }

    return (
        <Container maxWidth="md" sx={{ py: 3 }}>
            <Stack spacing={2}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'baseline' }}>
                    <Typography variant="overline" sx={{ color: 'text.secondary' }}>
                        Artifact
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {oid}
                    </Typography>
                </Stack>
                <WorkflowChainView oid={oid} />
            </Stack>
        </Container>
    );
};

export default ArtifactWorkflowPage;
