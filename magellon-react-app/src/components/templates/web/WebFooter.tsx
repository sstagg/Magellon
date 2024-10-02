import * as React from "react";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import {Grid} from "@mui/material";
import Box from "@mui/material/Box";
import {Facebook, Instagram, Twitter} from "@mui/icons-material";


export default function WebFooter() {
    return (

            <Container component="footer"  maxWidth={false}  disableGutters// This will ensure the container takes full width
                                   sx={{
                                       width: '100%',
                                       backgroundColor: (theme) =>
                                           theme.palette.mode === "light"
                                               ? theme.palette.grey[200]
                                               : theme.palette.grey[800],
                                       p: 6,
                                       boxSizing: 'border-box',
                                   }}>
                <Grid container spacing={5} sx={{ m: 0, p: 0 }}>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="h6" color="text.primary" gutterBottom>
                            About Magellon
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            We are Magellon, dedicated to providing the best service to our
                            customers.
                        </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="h6" color="text.primary" gutterBottom>
                            Contact Us
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            123 Main Street, Anytown, USA
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Email: info@example.com
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Phone: +1 234 567 8901
                        </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="h6" color="text.primary" gutterBottom>
                            Follow Us
                        </Typography>
                        <Link href="https://www.facebook.com/" color="inherit">
                            <Facebook />
                        </Link>
                        <Link
                            href="https://www.instagram.com/"
                            color="inherit"
                            sx={{ pl: 1, pr: 1 }}
                        >
                            <Instagram />
                        </Link>
                        <Link href="https://www.twitter.com/" color="inherit">
                            <Twitter />
                        </Link>
                    </Grid>
                </Grid>
                <Box mt={5}>
                    <Typography variant="body2" color="text.secondary" align="center">
                        {"Copyright © "}
                        <Link color="inherit" href="https://www.magellon.org/">
                            Magellon Website
                        </Link>{" "}
                        {new Date().getFullYear()}
                        {"."}
                    </Typography>
                </Box>
            </Container>

    );
}