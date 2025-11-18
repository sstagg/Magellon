import React from 'react';
import {
    Container,
    Typography,
    Link,
    Box,
    alpha,
    useTheme,
} from '@mui/material';

export default function ModernFooter() {
    const theme = useTheme();

    return (
        <Box
            component="footer"
            sx={{
                width: '100%',
                mt: 'auto',
                py: 3,
                borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                backgroundColor: alpha(theme.palette.background.default, 0.5),
            }}
        >
            <Container maxWidth="lg">
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: { xs: 'column', md: 'row' },
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 2,
                        textAlign: { xs: 'center', md: 'left' }
                    }}
                >
                    <Box>
                        <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
                            Magellon
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            © {new Date().getFullYear()} All rights reserved.
                        </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', justifyContent: 'center' }}>
                        <Link
                            href="/privacy"
                            color="text.secondary"
                            sx={{
                                textDecoration: 'none',
                                '&:hover': {
                                    color: 'primary.main',
                                    textDecoration: 'underline'
                                }
                            }}
                        >
                            Privacy Policy
                        </Link>
                        <Link
                            href="/terms"
                            color="text.secondary"
                            sx={{
                                textDecoration: 'none',
                                '&:hover': {
                                    color: 'primary.main',
                                    textDecoration: 'underline'
                                }
                            }}
                        >
                            Terms of Service
                        </Link>
                        <Link
                            href="/en/web/contact"
                            color="text.secondary"
                            sx={{
                                textDecoration: 'none',
                                '&:hover': {
                                    color: 'primary.main',
                                    textDecoration: 'underline'
                                }
                            }}
                        >
                            Contact
                        </Link>
                    </Box>
                </Box>
            </Container>
        </Box>
    );
}