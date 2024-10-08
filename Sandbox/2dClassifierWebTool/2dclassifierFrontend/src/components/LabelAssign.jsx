import { Box,Typography } from '@mui/material';

const LabelAssign=()=>{
    
    return(
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ border: '2px solid green', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', color: 'green' }}>
            1
          </Box>
          <Typography variant="body1">Best</Typography>
        </Box>
      
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ border: '2px solid blue', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', color: 'blue' }}>
            2
          </Box>
          <Typography variant="body1">Decent</Typography>
        </Box>
      
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ border: '2px solid orange', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', color: 'orange' }}>
            3
          </Box>
          <Typography variant="body1">Acceptable</Typography>
        </Box>
      
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ border: '2px solid red', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', color: 'red' }}>
            4
          </Box>
          <Typography variant="body1">Bad</Typography>
        </Box>
      
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ border: '2px solid darkred', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold', color: 'darkred' }}>
            5
          </Box>
          <Typography variant="body1">Unusable</Typography>
        </Box>
      </Box>
    )
}
export {LabelAssign}