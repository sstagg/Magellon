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
    CloudUpload
} from '@mui/icons-material';
import { Eye, EyeOff, User, Microscope, Shield, Database } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import magellonLogo from '../assets/images/magellon-logo.svg';

interface LoginFormData {
    username: string;
    password: string;
    rememberMe: boolean;
}

interface LoginPageViewProps {
    onLogin?: (credentials: LoginFormData) => Promise<boolean>;
}

const LoginPageView: React.FC<LoginPageViewProps> = ({ onLogin }) => {
    const theme = useTheme();
    const navigate = useNavigate();
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loginMode, setLoginMode] = useState<'login' | 'forgot'>('login');

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
            // Simulate API call - replace with actual authentication
            await new Promise(resolve => setTimeout(resolve, 1000));

            if (onLogin) {
                const success = await onLogin(data);
                if (!success) {
                    throw new Error('Invalid credentials');
                }
            }

            // Store token/credentials (replace with actual implementation)
            if (data.rememberMe) {
                localStorage.setItem('magellon_remember', 'true');
            }
            localStorage.setItem('magellon_user', JSON.stringify({
                username: data.username,
                token: 'mock-jwt-token'
            }));

            // Navigate to dashboard/main app
            navigate('/images');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    const handleForgotPassword = async (email: string) => {
        setLoading(true);
        try {
            // Simulate forgot password API call
            await new Promise(resolve => setTimeout(resolve, 1000));
            setError(null);
            // Show success message or redirect
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
                                            Sign in to your account to continue
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
                                                    InputProps={{
                                                        startAdornment: (
                                                            <InputAdornment position="start">
                                                                <User size={20} />
                                                            </InputAdornment>
                                                        )
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
                                                                >
                                                                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                                                                </IconButton>
                                                            </InputAdornment>
                                                        )
                                                    }}
                                                />

                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <FormControlLabel
                                                        control={<Checkbox {...register('rememberMe')} />}
                                                        label="Remember me"
                                                    />
                                                    <Link
                                                        component="button"
                                                        type="button"
                                                        variant="body2"
                                                        onClick={() => setLoginMode('forgot')}
                                                        sx={{ textDecoration: 'none' }}
                                                    >
                                                        Forgot password?
                                                    </Link>
                                                </Box>

                                                <Button
                                                    type="submit"
                                                    variant="contained"
                                                    size="large"
                                                    fullWidth
                                                    disabled={loading || !isValid}
                                                    endIcon={loading ? <CircularProgress size={20} /> : <ArrowForward />}
                                                    sx={{
                                                        py: 1.5,
                                                        fontSize: '1rem',
                                                        fontWeight: 600,
                                                        textTransform: 'none'
                                                    }}
                                                >
                                                    {loading ? 'Signing in...' : 'Sign In'}
                                                </Button>
                                            </Stack>
                                        </form>

                                        <Divider sx={{ my: 3 }}>
                                            <Typography variant="body2" color="text.secondary">
                                                Need access?
                                            </Typography>
                                        </Divider>

                                        <Typography variant="body2" color="text.secondary" align="center">
                                            Contact your administrator to request an account or{' '}
                                            <Link href="mailto:admin@magellon.org" sx={{ textDecoration: 'none' }}>
                                                email support
                                            </Link>
                                        </Typography>
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
                                                    InputProps={{
                                                        startAdornment: (
                                                            <InputAdornment position="start">
                                                                <Email />
                                                            </InputAdornment>
                                                        )
                                                    }}
                                                />

                                                <Button
                                                    type="submit"
                                                    variant="contained"
                                                    size="large"
                                                    fullWidth
                                                    disabled={loading}
                                                    endIcon={loading ? <CircularProgress size={20} /> : <ArrowForward />}
                                                    sx={{
                                                        py: 1.5,
                                                        fontSize: '1rem',
                                                        fontWeight: 600,
                                                        textTransform: 'none'
                                                    }}
                                                >
                                                    {loading ? 'Sending...' : 'Send Reset Instructions'}
                                                </Button>

                                                <Button
                                                    variant="text"
                                                    fullWidth
                                                    onClick={() => setLoginMode('login')}
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