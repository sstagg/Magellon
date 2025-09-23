import React, { useState } from 'react';
import {
    Box,
    Container,
    Paper,
    Typography,
    TextField,
    Button,
    FormControlLabel,
    Checkbox,
    Alert,
    InputAdornment,
    IconButton,
    Link,
    Divider,
    Stack,
    Card,
    CardContent,
    useTheme,
    alpha,
    CircularProgress,
    Fade,
    Slide
} from '@mui/material';
import {
    Visibility,
    VisibilityOff,
    Lock,
    Person,
    Email,
    ArrowForward,
    Science,
    Security,
    CloudUpload,
    Home
} from '@mui/icons-material';
import { Eye, EyeOff, User, Microscope, Shield, Database } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './UserManagement/AuthContext';
import magellonLogo from '../assets/images/magellon-logo.svg';

interface LoginFormData {
    username: string;
    password: string;
    rememberMe: boolean;
}

const LoginPageView: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const { login, loading: authLoading } = useAuth();

    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loginMode, setLoginMode] = useState<'login' | 'forgot'>('login');

    // Get the intended destination from location state, fallback to panel
    const from = location.state?.from?.pathname || '/en/panel/images';

    const {
        register,
        handleSubmit,
        formState: { errors, isValid },
        reset
    } = useForm<LoginFormData>({
        defaultValues: {
            username: '',
            password: '',
            rememberMe: false
        },
        mode: 'onChange'
    });

    const onSubmit = async (data: LoginFormData) => {
        setLoading(true);
        setError(null);

        try {
            // Use the AuthContext login method
            await login(data.username, data.password);

            // Store remember me preference
            if (data.rememberMe) {
                localStorage.setItem('magellon_remember', 'true');
            }

            // Navigate to intended destination
            navigate(from, { replace: true });
        } catch (err) {
            const errorMessage = (err as Error).message;
            setError(errorMessage || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    const handleForgotPassword = async (email: string) => {
        setLoading(true);
        try {
            // Simulate forgot password API call - replace with actual implementation
            await new Promise(resolve => setTimeout(resolve, 1000));
            setError(null);
            alert('Password reset instructions sent to your email');
            setLoginMode('login');
        } catch (err) {
            setError('Failed to send reset instructions');
        } finally {
            setLoading(false);
        }
    };

    const features = [
        {
            icon: <Microscope size={24} />,
            title: 'Microscopy Data Management',
            description: 'Advanced tools for cryo-EM and microscopy data organization'
        },
        {
            icon: <Database size={24} />,
            title: 'Session Import & Export',
            description: 'Seamless integration with Leginon, EPU, and other platforms'
        },
        {
            icon: <Shield size={24} />,
            title: 'Secure & Collaborative',
            description: 'Role-based access control and team collaboration features'
        }
    ];

    const isLoadingState = loading || authLoading;

    return (
        <Box
            sx={{
                height: '100vh',
                width: '100vw',
                position: 'fixed',
                top: 0,
                left: 0,
                background: theme.palette.mode === 'dark'
                    ? `linear-gradient(135deg, ${alpha('#0a1929', 0.95)} 0%, ${alpha('#1a2332', 0.95)} 100%)`
                    : `linear-gradient(135deg, ${alpha('#f5f7fa', 0.95)} 0%, ${alpha('#c3cfe2', 0.95)} 100%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
                zIndex: 9999
            }}
        >
            {/* Background Pattern */}
            <Box
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundImage: theme.palette.mode === 'dark'
                        ? 'radial-gradient(circle at 25% 25%, rgba(120, 119, 198, 0.1) 0%, transparent 50%), radial-gradient(circle at 75% 75%, rgba(255, 255, 255, 0.05) 0%, transparent 50%)'
                        : 'radial-gradient(circle at 25% 25%, rgba(74, 144, 226, 0.1) 0%, transparent 50%), radial-gradient(circle at 75% 75%, rgba(74, 144, 226, 0.05) 0%, transparent 50%)',
                    zIndex: 0
                }}
            />

            {/* Home Button */}
            <Box sx={{ position: 'absolute', top: 24, left: 24, zIndex: 10 }}>
                <Button
                    startIcon={<Home />}
                    onClick={() => navigate('/en/web/home')}
                    sx={{
                        color: 'text.secondary',
                        '&:hover': {
                            color: 'primary.main',
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        }
                    }}
                >
                    Back to Home
                </Button>
            </Box>

            <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {/* Left Side - Branding and Features */}
                    <Box sx={{ flex: 1, display: { xs: 'none', md: 'block' } }}>
                        <Fade in timeout={800}>
                            <Box>
                                {/* Logo and Branding */}
                                <Box sx={{ mb: 6 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                                        <img
                                            src={magellonLogo}
                                            alt="Magellon"
                                            style={{
                                                height: 48,
                                                marginRight: 16,
                                                filter: theme.palette.mode === 'dark' ? 'brightness(0) invert(1)' : 'none'
                                            }}
                                        />
                                        <Typography
                                            variant="h3"
                                            sx={{
                                                fontFamily: 'Exo 2',
                                                fontWeight: 'bold',
                                                background: theme.palette.mode === 'dark'
                                                    ? 'linear-gradient(45deg, #fff 30%, #a5b4fc 90%)'
                                                    : 'linear-gradient(45deg, #1976d2 30%, #42a5f5 90%)',
                                                backgroundClip: 'text',
                                                WebkitBackgroundClip: 'text',
                                                color: 'transparent'
                                            }}
                                        >
                                            Magellon
                                        </Typography>
                                    </Box>
                                    <Typography
                                        variant="h5"
                                        sx={{
                                            color: 'text.primary',
                                            fontWeight: 300,
                                            mb: 2
                                        }}
                                    >
                                        Advanced Microscopy Data Platform
                                    </Typography>
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            color: 'text.secondary',
                                            maxWidth: 480,
                                            lineHeight: 1.6
                                        }}
                                    >
                                        Streamline your cryo-EM workflows with powerful data management,
                                        processing pipelines, and collaborative research tools.
                                    </Typography>
                                </Box>

                                {/* Features */}
                                <Stack spacing={3}>
                                    {features.map((feature, index) => (
                                        <Slide
                                            key={index}
                                            direction="right"
                                            in
                                            timeout={1000 + index * 200}
                                        >
                                            <Card
                                                elevation={0}
                                                sx={{
                                                    background: alpha(theme.palette.background.paper, 0.6),
                                                    backdropFilter: 'blur(10px)',
                                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                                                }}
                                            >
                                                <CardContent sx={{ p: 3 }}>
                                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                                                        <Box
                                                            sx={{
                                                                p: 1.5,
                                                                borderRadius: 2,
                                                                background: alpha(theme.palette.primary.main, 0.1),
                                                                color: 'primary.main'
                                                            }}
                                                        >
                                                            {feature.icon}
                                                        </Box>
                                                        <Box>
                                                            <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                                                                {feature.title}
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                {feature.description}
                                                            </Typography>
                                                        </Box>
                                                    </Box>
                                                </CardContent>
                                            </Card>
                                        </Slide>
                                    ))}
                                </Stack>
                            </Box>
                        </Fade>
                    </Box>

                    {/* Right Side - Login Form */}
                    <Box sx={{ width: { xs: '100%', md: 400 } }}>
                        <Slide direction="left" in timeout={800}>
                            <Paper
                                elevation={theme.palette.mode === 'dark' ? 0 : 8}
                                sx={{
                                    p: 4,
                                    borderRadius: 3,
                                    background: alpha(theme.palette.background.paper, 0.95),
                                    backdropFilter: 'blur(20px)',
                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                                }}
                            >
                                {/* Mobile Logo */}
                                <Box sx={{ display: { xs: 'flex', md: 'none' }, alignItems: 'center', justifyContent: 'center', mb: 4 }}>
                                    <img
                                        src={magellonLogo}
                                        alt="Magellon"
                                        style={{
                                            height: 32,
                                            marginRight: 12,
                                            filter: theme.palette.mode === 'dark' ? 'brightness(0) invert(1)' : 'none'
                                        }}
                                    />
                                    <Typography
                                        variant="h5"
                                        sx={{
                                            fontFamily: 'Exo 2',
                                            fontWeight: 'bold',
                                            color: 'primary.main'
                                        }}
                                    >
                                        Magellon
                                    </Typography>
                                </Box>

                                {loginMode === 'login' ? (
                                    <>
                                        <Typography variant="h4" sx={{ mb: 1, fontWeight: 600 }}>
                                            Welcome back
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                                            Sign in to your CryoEM analysis platform
                                        </Typography>

                                        {error && (
                                            <Alert severity="error" sx={{ mb: 3 }}>
                                                {error}
                                            </Alert>
                                        )}

                                        <form onSubmit={handleSubmit(onSubmit)}>
                                            <Stack spacing={3}>
                                                <TextField
                                                    fullWidth
                                                    label="Username or Email"
                                                    variant="outlined"
                                                    {...register('username', {
                                                        required: 'Username is required',
                                                        minLength: {
                                                            value: 3,
                                                            message: 'Username must be at least 3 characters'
                                                        }
                                                    })}
                                                    error={!!errors.username}
                                                    helperText={errors.username?.message}
                                                    disabled={isLoadingState}
                                                    InputProps={{
                                                        startAdornment: (
                                                            <InputAdornment position="start">
                                                                <User size={20} />
                                                            </InputAdornment>
                                                        )
                                                    }}
                                                    sx={{
                                                        '& .MuiOutlinedInput-root': {
                                                            borderRadius: 2,
                                                            transition: 'all 0.3s ease',
                                                            '&:hover': {
                                                                '& .MuiOutlinedInput-notchedOutline': {
                                                                    borderColor: 'primary.main',
                                                                }
                                                            },
                                                            '&.Mui-focused': {
                                                                '& .MuiOutlinedInput-notchedOutline': {
                                                                    borderColor: 'primary.main',
                                                                    borderWidth: 2,
                                                                }
                                                            }
                                                        }
                                                    }}
                                                />

                                                <TextField
                                                    fullWidth
                                                    label="Password"
                                                    type={showPassword ? 'text' : 'password'}
                                                    variant="outlined"
                                                    {...register('password', {
                                                        required: 'Password is required',
                                                        minLength: {
                                                            value: 6,
                                                            message: 'Password must be at least 6 characters'
                                                        }
                                                    })}
                                                    error={!!errors.password}
                                                    helperText={errors.password?.message}
                                                    disabled={isLoadingState}
                                                    InputProps={{
                                                        startAdornment: (
                                                            <InputAdornment position="start">
                                                                <Lock />
                                                            </InputAdornment>
                                                        ),
                                                        endAdornment: (
                                                            <InputAdornment position="end">
                                                                <IconButton
                                                                    onClick={() => setShowPassword(!showPassword)}
                                                                    edge="end"
                                                                    disabled={isLoadingState}
                                                                >
                                                                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                                                                </IconButton>
                                                            </InputAdornment>
                                                        )
                                                    }}
                                                    sx={{
                                                        '& .MuiOutlinedInput-root': {
                                                            borderRadius: 2,
                                                            transition: 'all 0.3s ease',
                                                            '&:hover': {
                                                                '& .MuiOutlinedInput-notchedOutline': {
                                                                    borderColor: 'primary.main',
                                                                }
                                                            },
                                                            '&.Mui-focused': {
                                                                '& .MuiOutlinedInput-notchedOutline': {
                                                                    borderColor: 'primary.main',
                                                                    borderWidth: 2,
                                                                }
                                                            }
                                                        }
                                                    }}
                                                />

                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <FormControlLabel
                                                        control={
                                                            <Checkbox
                                                                {...register('rememberMe')}
                                                                disabled={isLoadingState}
                                                            />
                                                        }
                                                        label="Remember me"
                                                    />
                                                    <Link
                                                        component="button"
                                                        type="button"
                                                        variant="body2"
                                                        onClick={() => setLoginMode('forgot')}
                                                        disabled={isLoadingState}
                                                        sx={{
                                                            textDecoration: 'none',
                                                            '&:hover': {
                                                                textDecoration: 'underline'
                                                            }
                                                        }}
                                                    >
                                                        Forgot password?
                                                    </Link>
                                                </Box>

                                                <Button
                                                    type="submit"
                                                    variant="contained"
                                                    size="large"
                                                    fullWidth
                                                    disabled={isLoadingState || !isValid}
                                                    endIcon={isLoadingState ? <CircularProgress size={20} /> : <ArrowForward />}
                                                    sx={{
                                                        py: 1.5,
                                                        fontSize: '1rem',
                                                        fontWeight: 600,
                                                        textTransform: 'none',
                                                        borderRadius: 3,
                                                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                        boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
                                                        transition: 'all 0.3s ease',
                                                        '&:hover': {
                                                            background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                                                            transform: 'translateY(-2px)',
                                                            boxShadow: '0 12px 40px rgba(102, 126, 234, 0.4)',
                                                        },
                                                        '&:disabled': {
                                                            background: alpha(theme.palette.action.disabled, 0.3),
                                                            color: alpha(theme.palette.action.disabled, 0.7),
                                                            transform: 'none',
                                                            boxShadow: 'none',
                                                        }
                                                    }}
                                                >
                                                    {isLoadingState ? 'Signing in...' : 'Sign In'}
                                                </Button>
                                            </Stack>
                                        </form>

                                        <Divider sx={{ my: 3 }}>
                                            <Typography variant="body2" color="text.secondary">
                                                Need access?
                                            </Typography>
                                        </Divider>

                                        <Box sx={{ textAlign: 'center' }}>
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                                Don't have an account? Contact your administrator.
                                            </Typography>

                                            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
                                                <Link
                                                    component="button"
                                                    type="button"
                                                    variant="body2"
                                                    onClick={() => navigate('/en/web/contact')}
                                                    sx={{
                                                        textDecoration: 'none',
                                                        color: 'text.secondary',
                                                        '&:hover': {
                                                            color: 'primary.main',
                                                            textDecoration: 'underline',
                                                        }
                                                    }}
                                                >
                                                    Contact Support
                                                </Link>
                                                <Typography variant="body2" color="text.disabled">•</Typography>
                                                <Link
                                                    href="mailto:admin@magellon.org"
                                                    sx={{
                                                        textDecoration: 'none',
                                                        color: 'text.secondary',
                                                        '&:hover': {
                                                            color: 'primary.main',
                                                            textDecoration: 'underline',
                                                        }
                                                    }}
                                                >
                                                    Email Support
                                                </Link>
                                            </Box>
                                        </Box>
                                    </>
                                ) : (
                                    <>
                                        <Typography variant="h4" sx={{ mb: 1, fontWeight: 600 }}>
                                            Reset Password
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                                            Enter your email address and we'll send you reset instructions
                                        </Typography>

                                        {error && (
                                            <Alert severity="error" sx={{ mb: 3 }}>
                                                {error}
                                            </Alert>
                                        )}

                                        <form onSubmit={(e) => {
                                            e.preventDefault();
                                            const formData = new FormData(e.currentTarget);
                                            const email = formData.get('email') as string;
                                            handleForgotPassword(email);
                                        }}>
                                            <Stack spacing={3}>
                                                <TextField
                                                    fullWidth
                                                    name="email"
                                                    label="Email Address"
                                                    type="email"
                                                    variant="outlined"
                                                    required
                                                    disabled={isLoadingState}
                                                    InputProps={{
                                                        startAdornment: (
                                                            <InputAdornment position="start">
                                                                <Email />
                                                            </InputAdornment>
                                                        )
                                                    }}
                                                    sx={{
                                                        '& .MuiOutlinedInput-root': {
                                                            borderRadius: 2,
                                                        }
                                                    }}
                                                />

                                                <Button
                                                    type="submit"
                                                    variant="contained"
                                                    size="large"
                                                    fullWidth
                                                    disabled={isLoadingState}
                                                    endIcon={isLoadingState ? <CircularProgress size={20} /> : <ArrowForward />}
                                                    sx={{
                                                        py: 1.5,
                                                        fontSize: '1rem',
                                                        fontWeight: 600,
                                                        textTransform: 'none',
                                                        borderRadius: 3
                                                    }}
                                                >
                                                    {isLoadingState ? 'Sending...' : 'Send Reset Instructions'}
                                                </Button>

                                                <Button
                                                    variant="text"
                                                    fullWidth
                                                    onClick={() => setLoginMode('login')}
                                                    disabled={isLoadingState}
                                                    sx={{ textTransform: 'none' }}
                                                >
                                                    Back to Sign In
                                                </Button>
                                            </Stack>
                                        </form>
                                    </>
                                )}
                            </Paper>
                        </Slide>
                    </Box>
                </Box>
            </Container>
        </Box>
    );
};

export default LoginPageView;