import React from "react";
import { Grid, Card, CardContent, Typography } from "@mui/material";

const InfoCards = ({ defocus1Micrometers, defocus2Micrometers, angleAstigmatismDegrees, resolutionAngstroms }) => {
    // Convert values
    // const defocus1Micrometers = (defocus1 * 1e6).toFixed(2); // Defocus 1 in μm
    // const defocus2Micrometers = (defocus2 * 1e6).toFixed(2); // Defocus 2 in μm
    // const angleAstigmatismDegrees = (angleAstigmatism * (180 / Math.PI)).toFixed(2); // Angle astigmatism in °
    // const resolutionAngstroms = resolution50Percent.toFixed(2); // Resolution 50% in Å
    return (
        <div style={{  display: "flex", justifyContent: "center", alignItems: "center" ,padding:"15px" }}>

            <Grid container spacing={4} justifyContent="center" style={{ width: '100%' }}>
                {/* Defocus 1 */}
                <Grid item xs={12} sm={6} md={3} style={{ flexBasis: '25%', height: '25%' }}>
                    <Card style={{ height: '100%' }}>
                        <CardContent style={{ textAlign: "center" }}>
                            <Typography variant="h4" component="div" color="primary" style={{ fontWeight: 'bold' }}>
                                {defocus1Micrometers} μm
                            </Typography>
                            <Typography variant="body2" component="div" color="textSecondary" style={{ fontSize: '0.875rem' }}>
                                Defocus 1
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Defocus 2 */}
                <Grid item xs={12} sm={6} md={3} style={{ flexBasis: '25%', height: '25%' }}>
                    <Card style={{ height: '100%' }}>
                        <CardContent style={{ textAlign: "center" }}>
                            <Typography variant="h4" component="div" color="primary" style={{ fontWeight: 'bold' }}>
                                {defocus2Micrometers} μm
                            </Typography>
                            <Typography variant="body2" component="div" color="textSecondary" style={{ fontSize: '0.875rem' }}>
                                Defocus 2
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Angle Astigmatism */}
                <Grid item xs={12} sm={6} md={3} style={{ flexBasis: '25%', height: '25%' }}>
                    <Card style={{ height: '100%' }}>
                        <CardContent style={{ textAlign: "center" }}>
                            <Typography variant="h4" component="div" color="primary" style={{ fontWeight: 'bold' }}>
                                {angleAstigmatismDegrees} °
                            </Typography>
                            <Typography variant="body2" component="div" color="textSecondary" style={{ fontSize: '0.875rem' }}>
                                Angle Astigmatism
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Resolution */}
                <Grid item xs={12} sm={6} md={3} style={{ flexBasis: '25%', height: '25%' }}>
                    <Card style={{ height: '100%' }}>
                        <CardContent style={{ textAlign: "center" }}>
                            <Typography variant="h4" component="div" color="primary" style={{ fontWeight: 'bold' }}>
                                {resolutionAngstroms} Å
                            </Typography>
                            <Typography variant="body2" component="div" color="textSecondary" style={{ fontSize: '0.875rem' }}>
                                Resolution 50%
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </div>
    );
};

export default InfoCards;