import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Paper,
    Card,
    CardContent,
    CardHeader,
    Avatar,
    Chip,
    Button,
    IconButton,
    Divider,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Alert,
    Link,
    Stack,
    Tooltip,
    Badge,
    LinearProgress,
    useTheme,
    alpha,
    Fade,
    Zoom,
    useMediaQuery
} from '@mui/material';

import Grid from '@mui/material/Grid';


import { Timeline, TimelineItem, TimelineConnector, TimelineContent, TimelineDot, TimelineSeparator } from '@mui/lab';

import {
    Science,
    Memory,
    Speed,
    Security,
    CloudSync,
    GitHub,
    Email,
    LinkedIn,
    Twitter,
    Launch,
    Code,
    BugReport,
    Lightbulb,
    School,
    Business,
    People,
    Star,
    TrendingUp,
    Assessment,
    Extension,
    ExpandMore,
    CheckCircle,
    Update,
    Favorite,
    Public,
    Download,
    Share
} from '@mui/icons-material';

import {
    Microscope,
    Atom,
    Database,
    Zap,
    Shield,
    Users,
    Globe,
    Award,
    BookOpen,
    Heart,
    Coffee,
    Cpu,
    HardDrive,
    Network,
    Eye,
    Filter,
    Search,
    BarChart3,
    Layers,
    Target,
    Settings
} from 'lucide-react';
import magellonLogo from "../../../assets/images/magellon-logo.svg";

const DRAWER_WIDTH = 240;

// Team member interface
interface TeamMember {
    name: string;
    role: string;
    bio: string;
    avatar?: string;
    expertise: string[];
    social?: {
        github?: string;
        linkedin?: string;
        email?: string;
        twitter?: string;
    };
}

// Feature interface
interface Feature {
    title: string;
    description: string;
    icon: React.ReactNode;
    category: 'core' | 'analysis' | 'performance' | 'ui';
    status: 'stable' | 'beta' | 'experimental';
}

// Technology interface
interface Technology {
    name: string;
    version: string;
    description: string;
    category: 'frontend' | 'backend' | 'database' | 'infrastructure';
    icon?: React.ReactNode;
}

const AboutPage: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    const [selectedFeatureCategory, setSelectedFeatureCategory] = useState<string>('all');
    const [showSystemInfo, setShowSystemInfo] = useState(false);

    // Track drawer state from localStorage to adjust layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Listen for drawer state changes
    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    // Team data
    const teamMembers: TeamMember[] = [
        {
            name: "Scott Stagg",
            role: "Principal Investigator & Director",
            bio: "Professor of Biological Sciences at Florida State University and director of the SECM4 facility. Expert in cryo-EM methodology development and high-throughput structural biology with focus on membrane trafficking mechanisms.",
            expertise: ["Cryo-EM", "Membrane Biology", "COPII Vesicles", "Method Development", "High-throughput Analysis"],
            social: {
                github: "https://github.com/sstagg/Magellon",
                linkedin: "",
                email: "sstagg@fsu.edu"
            }
        },
        {
            name: "Gabe Lander",
            role: "Principal Investigator",
            bio: "Professor in the Department of Integrative Structural and Computational Biology at Scripps Research Institute. Pioneer in advancing cryo-EM accessibility and expert in protein quality control mechanisms.",
            expertise: ["Structural Biology", "AAA+ Proteases", "Cryo-EM Methodology", "Protein Degradation", "Small Molecule Interactions"],
            social: {
                linkedin: "https://www.linkedin.com/in/gabriel-lander-910b699/",
                email: "glander@scripps.edu"
            }
        },
        {
            name: "Michael Cianfrocco",
            role: "Principal Investigator",
            bio: "Assistant Professor at University of Michigan Life Sciences Institute. Expert in microtubule-based transport, cryo-EM automation, and cloud computing solutions for structural biology.",
            expertise: ["Cryo-EM Automation", "Cloud Computing", "Microtubule Biology", "AI/ML in Structural Biology", "High-throughput Processing"],
            social: {
                github: "https://github.com/cianfrocco-lab",
                twitter: "",
                email: "mcianfro@umich.edu"
            }
        },
        {
            name: "Behdad Khoshbin",
            role: "Lead Developer",
            bio: "Software engineer and project manager specializing in software development. Expert in system design, user interface design, and system architecture for research applications.",
            expertise: ["System Design", "System Architecture", "Project Management", "Scientific Software", "UI/UX Design"],
            social: {
                linkedin: "https://www.linkedin.com/in/behdad-khoshbin-b40161128/",
                email: "b.khoshbin@gmail.com"
            }
        },
        {
            name: "Puneeth Reddy",
            role: "Developer",
            bio: "Graduate student and software developer at Florida State University. Focuses on implementing advanced image processing algorithms and user interface components for scientific workflows.",
            expertise: ["Image Processing", "Frontend Development", "Algorithm Implementation", "Scientific Computing", "React Development"],
            social: {
                linkedin: "",
                email: "pm22p@fsu.edu"
            }
        }
    ];

    // Features data
    const features: Feature[] = [
        {
            title: "Advanced Image Processing",
            description: "Real-time brightness, contrast, and gamma correction with histogram analysis",
            icon: <Eye size={20} />,
            category: 'core',
            status: 'stable'
        },
        {
            title: "Multi-format Support",
            description: "Support for MRC, TIFF, JPEG, and other scientific image formats",
            icon: <Layers size={20} />,
            category: 'core',
            status: 'stable'
        },
        {
            title: "Particle Picking",
            description: "Interactive particle selection and automated picking algorithms",
            icon: <Target size={20} />,
            category: 'analysis',
            status: 'stable'
        },
        {
            title: "CTF Analysis",
            description: "Contrast Transfer Function visualization and analysis tools",
            icon: <BarChart3 size={20} />,
            category: 'analysis',
            status: 'stable'
        },
        {
            title: "Virtual Scrolling",
            description: "High-performance rendering of large image datasets",
            icon: <Zap size={20} />,
            category: 'performance',
            status: 'stable'
        },
        {
            title: "Advanced Filtering",
            description: "Multi-parameter filtering with real-time search capabilities",
            icon: <Filter size={20} />,
            category: 'ui',
            status: 'stable'
        },
        {
            title: "Metadata Explorer",
            description: "Hierarchical metadata browsing with JSON visualization",
            icon: <Database size={20} />,
            category: 'analysis',
            status: 'stable'
        },
        {
            title: "Comparison Mode",
            description: "Side-by-side comparison of multiple images",
            icon: <Settings size={20} />,
            category: 'ui',
            status: 'beta'
        },
        {
            title: "AI-Powered Analysis",
            description: "Machine learning integration for automated analysis",
            icon: <Cpu size={20} />,
            category: 'analysis',
            status: 'experimental'
        }
    ];

    // Technologies data
    const technologies: Technology[] = [
        {
            name: "React",
            version: "19.1.0",
            description: "Modern UI framework for responsive interfaces",
            category: 'frontend',
            icon: <Code />
        },
        {
            name: "TypeScript",
            version: "5.8.3",
            description: "Type-safe JavaScript for robust development",
            category: 'frontend',
            icon: <Code />
        },
        {
            name: "Material-UI",
            version: "7.1.0",
            description: "Professional React component library",
            category: 'frontend',
            icon: <Extension />
        },
        {
            name: "Zustand",
            version: "5.0.3",
            description: "Lightweight state management solution",
            category: 'frontend',
            icon: <Memory />
        },
        {
            name: "FastAPI",
            version: "Latest",
            description: "High-performance Python web framework",
            category: 'backend',
            icon: <Speed />
        },
        {
            name: "MySql",
            version: "8+",
            description: "Advanced relational database system",
            category: 'database',
            icon: <HardDrive />
        }
    ];

    // Version history
    const versionHistory = [
        {
            version: "1.0.0",
            date: "2025-01-15",
            description: "Initial release with core image viewing capabilities",
            features: ["Basic image viewing", "Session management", "Atlas navigation"]
        },
        {
            version: "1.1.0",
            date: "2025-02-01",
            description: "Enhanced processing and particle picking",
            features: ["Particle picking editor", "CTF analysis", "Metadata explorer"]
        },
        {
            version: "1.2.0",
            date: "2025-03-01",
            description: "Performance optimizations and UI improvements",
            features: ["Virtual scrolling", "Advanced filtering", "Responsive design"]
        },
        {
            version: "1.3.0",
            date: "2025-04-01",
            description: "Collaboration and comparison features",
            features: ["Comparison mode", "User preferences", "Workflow automation"]
        }
    ];

    // System requirements
    const systemRequirements = {
        minimum: {
            cpu: "Intel i5-8400 / AMD Ryzen 5 2600",
            memory: "8 GB RAM",
            storage: "500 MB available space",
            browser: "Chrome 90+, Firefox 88+, Safari 14+",
            network: "Broadband Internet connection"
        },
        recommended: {
            cpu: "Intel i7-10700K / AMD Ryzen 7 3700X",
            memory: "16 GB RAM",
            storage: "2 GB available space",
            browser: "Chrome 100+, Firefox 95+",
            network: "High-speed Internet connection"
        }
    };

    const filteredFeatures = selectedFeatureCategory === 'all'
        ? features
        : features.filter(f => f.category === selectedFeatureCategory);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'stable': return 'success';
            case 'beta': return 'warning';
            case 'experimental': return 'info';
            default: return 'default';
        }
    };

    const getCategoryIcon = (category: string) => {
        switch (category) {
            case 'core': return <Science />;
            case 'analysis': return <Assessment />;
            case 'performance': return <Speed />;
            case 'ui': return <Extension />;
            default: return <Star />;
        }
    };

    return (
        <Box sx={{
            position: 'fixed',
            top: 64, // Account for header
            left: leftMargin,
            right: 0,
            bottom: 0,
            zIndex: 1050, // Below drawer but above content
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Scrollable Content Container */}
            <Box sx={{
                flex: 1,
                overflow: 'auto',
                p: { xs: 2, sm: 3, md: 4 }
            }}>
                {/* Hero Section */}
                <Box sx={{ textAlign: 'center', mb: { xs: 4, md: 6 } }}>
                    <Zoom in={true} timeout={1000}>
                        <Box sx={{ mb: 3 }}>
                            <img
                                src={magellonLogo}
                                alt="Magellon Logo"
                                style={{
                                    height: isMobile ? 60 : isTablet ? 70 : 80,
                                    marginBottom: 16
                                }}
                            />
                            <Typography
                                variant={isMobile ? "h3" : "h2"}
                                component="h1"
                                fontWeight="bold"
                                gutterBottom
                                sx={{ fontSize: { xs: '2rem', sm: '2.5rem', md: '3.75rem' } }}
                            >
                                Magellon
                            </Typography>
                            <Typography
                                variant={isMobile ? "h6" : "h5"}
                                color="text.secondary"
                                sx={{
                                    mb: 3,
                                    fontSize: { xs: '1.1rem', sm: '1.25rem', md: '1.5rem' }
                                }}
                            >
                                Advanced Scientific Image Analysis Platform
                            </Typography>
                            <Typography
                                variant="body1"
                                sx={{
                                    maxWidth: 800,
                                    mx: 'auto',
                                    mb: 4,
                                    fontSize: { xs: '0.9rem', sm: '1rem', md: '1.1rem' },
                                    px: { xs: 1, sm: 2 }
                                }}
                            >
                                Empowering researchers with cutting-edge tools for cryo-electron microscopy
                                image analysis, processing, and visualization. Built by scientists, for scientists.
                            </Typography>
                            <Stack
                                direction={{ xs: 'column', sm: 'row' }}
                                spacing={2}
                                justifyContent="center"
                                sx={{ px: { xs: 2, sm: 0 } }}
                            >
                                <Button
                                    variant="contained"
                                    size={isMobile ? "medium" : "large"}
                                    startIcon={<Download />}
                                    href="https://www.magellon.org/"
                                    fullWidth={isMobile}
                                >
                                    Get Started
                                </Button>
                                <Button
                                    variant="outlined"
                                    size={isMobile ? "medium" : "large"}
                                    startIcon={<GitHub />}
                                    href="https://github.com/sstagg/Magellon"
                                    target="_blank"
                                    fullWidth={isMobile}
                                >
                                    View Source
                                </Button>
                            </Stack>
                        </Box>
                    </Zoom>
                </Box>

                {/* Vision Statement */}
                <Paper
                    elevation={2}
                    sx={{
                        p: { xs: 3, sm: 4 },
                        mb: { xs: 4, md: 6 },
                        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.1)}, ${alpha(theme.palette.secondary.main, 0.1)})`
                    }}
                >
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Our Vision
                    </Typography>
                    <Typography
                        variant="body1"
                        sx={{
                            fontSize: { xs: '1rem', sm: '1.1rem' },
                            lineHeight: 1.8,
                            textAlign: 'center',
                            maxWidth: 800,
                            mx: 'auto'
                        }}
                    >
                        We envision a seamless workflow where cryo-EM data collection and analysis become
                        <strong> decoupled geographically while remaining integrated operationally</strong>.
                        Magellon enables researchers to access world-class microscopes and computational resources
                        without capital investment in hardware, while maintaining a unified interface that handles
                        the complexity of distributed computing behind the scenes.
                    </Typography>
                </Paper>

                {/* Key Features Overview */}
                <Paper elevation={2} sx={{ p: { xs: 3, sm: 4 }, mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Why Choose Magellon?
                    </Typography>
                    <Grid container spacing={4} sx={{ mt: 2 }}>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Box textAlign="center">
                                <Avatar sx={{
                                    width: { xs: 60, sm: 80 },
                                    height: { xs: 60, sm: 80 },
                                    mx: 'auto',
                                    mb: 2,
                                    bgcolor: 'primary.main'
                                }}>
                                    <Microscope size={isMobile ? 30 : 40} />
                                </Avatar>
                                <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' } }}>
                                    Scientific Precision
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: { xs: '0.85rem', sm: '0.875rem' } }}>
                                    Built specifically for cryo-EM workflows with accuracy and reproducibility at its core
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Box textAlign="center">
                                <Avatar sx={{
                                    width: { xs: 60, sm: 80 },
                                    height: { xs: 60, sm: 80 },
                                    mx: 'auto',
                                    mb: 2,
                                    bgcolor: 'secondary.main'
                                }}>
                                    <Speed size={isMobile ? 30 : 40} />
                                </Avatar>
                                <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' } }}>
                                    High Performance
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: { xs: '0.85rem', sm: '0.875rem' } }}>
                                    Optimized for large datasets with virtual scrolling and efficient memory management
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Box textAlign="center">
                                <Avatar sx={{
                                    width: { xs: 60, sm: 80 },
                                    height: { xs: 60, sm: 80 },
                                    mx: 'auto',
                                    mb: 2,
                                    bgcolor: 'success.main'
                                }}>
                                    <Users size={isMobile ? 30 : 40} />
                                </Avatar>
                                <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' } }}>
                                    User-Centric Design
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: { xs: '0.85rem', sm: '0.875rem' } }}>
                                    Intuitive interface designed by researchers who understand scientific workflows
                                </Typography>
                            </Box>
                        </Grid>
                    </Grid>
                </Paper>

                {/* Features Section */}
                <Box sx={{ mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Features
                    </Typography>

                    {/* Feature category filter */}
                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
                        <Stack
                            direction={{ xs: 'column', sm: 'row' }}
                            spacing={1}
                            sx={{ width: { xs: '100%', sm: 'auto' } }}
                        >
                            {['all', 'core', 'analysis', 'performance', 'ui'].map((category) => (
                                <Button
                                    key={category}
                                    variant={selectedFeatureCategory === category ? 'contained' : 'outlined'}
                                    onClick={() => setSelectedFeatureCategory(category)}
                                    startIcon={category !== 'all' ? getCategoryIcon(category) : <Star />}
                                    size="small"
                                    fullWidth={isMobile}
                                    sx={{ textTransform: 'none' }}
                                >
                                    {category.charAt(0).toUpperCase() + category.slice(1)}
                                </Button>
                            ))}
                        </Stack>
                    </Box>

                    <Grid container spacing={3}>
                        {filteredFeatures.map((feature, index) => (
                            <Grid key={feature.title} size={{ xs: 12, sm: 6, md: 4 }}>
                                <Fade in={true} timeout={500 + index * 100}>
                                    <Card sx={{
                                        height: '100%',
                                        transition: 'transform 0.2s',
                                        '&:hover': { transform: 'translateY(-4px)' }
                                    }}>
                                        <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                                <Avatar sx={{
                                                    mr: 2,
                                                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                                                    width: { xs: 40, sm: 48 },
                                                    height: { xs: 40, sm: 48 }
                                                }}>
                                                    {feature.icon}
                                                </Avatar>
                                                <Box sx={{ flex: 1 }}>
                                                    <Typography
                                                        variant="h6"
                                                        gutterBottom
                                                        sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
                                                    >
                                                        {feature.title}
                                                    </Typography>
                                                    <Chip
                                                        label={feature.status}
                                                        size="small"
                                                        color={getStatusColor(feature.status) as any}
                                                        variant="outlined"
                                                    />
                                                </Box>
                                            </Box>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{ fontSize: { xs: '0.85rem', sm: '0.875rem' } }}
                                            >
                                                {feature.description}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Fade>
                            </Grid>
                        ))}
                    </Grid>
                </Box>

                {/* Technology Stack */}
                <Paper elevation={2} sx={{ p: { xs: 3, sm: 4 }, mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Technology Stack
                    </Typography>
                    <Grid container spacing={3} sx={{ mt: 2 }}>
                        {technologies.map((tech) => (
                            <Grid key={tech.name} size={{ xs: 12, sm: 6, md: 4 }}>
                                <Card variant="outlined" sx={{ height: '100%' }}>
                                    <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                            <Box sx={{ mr: 2 }}>
                                                {tech.icon}
                                            </Box>
                                            <Box>
                                                <Typography
                                                    variant="h6"
                                                    sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
                                                >
                                                    {tech.name}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    v{tech.version}
                                                </Typography>
                                            </Box>
                                        </Box>
                                        <Typography
                                            variant="body2"
                                            color="text.secondary"
                                            sx={{ fontSize: { xs: '0.85rem', sm: '0.875rem' } }}
                                        >
                                            {tech.description}
                                        </Typography>
                                        <Chip
                                            label={tech.category}
                                            size="small"
                                            sx={{ mt: 1 }}
                                            variant="outlined"
                                        />
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>
                </Paper>

                {/* Team Section */}
                <Box sx={{ mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Meet the Team
                    </Typography>
                    <Grid container spacing={4} sx={{ mt: 2 }}>
                        {teamMembers.map((member, index) => (
                            <Grid key={member.name} size={{ xs: 12, sm: 6, md: 6, lg: 3 }}>
                                <Zoom in={true} timeout={800 + index * 200}>
                                    <Card sx={{ height: '100%', textAlign: 'center' }}>
                                        <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                                            <Avatar
                                                sx={{
                                                    width: { xs: 60, sm: 80 },
                                                    height: { xs: 60, sm: 80 },
                                                    mx: 'auto',
                                                    mb: 2,
                                                    bgcolor: 'primary.main',
                                                    fontSize: { xs: '1.5rem', sm: '2rem' }
                                                }}
                                            >
                                                {member.name.split(' ').map(n => n[0]).join('')}
                                            </Avatar>
                                            <Typography
                                                variant="h6"
                                                gutterBottom
                                                sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
                                            >
                                                {member.name}
                                            </Typography>
                                            <Typography
                                                variant="subtitle2"
                                                color="primary"
                                                gutterBottom
                                                sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
                                            >
                                                {member.role}
                                            </Typography>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{
                                                    mb: 2,
                                                    fontSize: { xs: '0.8rem', sm: '0.875rem' }
                                                }}
                                            >
                                                {member.bio}
                                            </Typography>
                                            <Stack
                                                direction="row"
                                                spacing={0.5}
                                                sx={{
                                                    mb: 2,
                                                    flexWrap: 'wrap',
                                                    justifyContent: 'center',
                                                    gap: 0.5
                                                }}
                                            >
                                                {member.expertise.map((skill) => (
                                                    <Chip
                                                        key={skill}
                                                        label={skill}
                                                        size="small"
                                                        variant="outlined"
                                                        sx={{ fontSize: { xs: '0.7rem', sm: '0.75rem' } }}
                                                    />
                                                ))}
                                            </Stack>
                                            <Stack direction="row" spacing={1} justifyContent="center">
                                                {member.social?.github && (
                                                    <IconButton size="small" href={member.social.github} target="_blank">
                                                        <GitHub />
                                                    </IconButton>
                                                )}
                                                {member.social?.linkedin && (
                                                    <IconButton size="small" href={member.social.linkedin} target="_blank">
                                                        <LinkedIn />
                                                    </IconButton>
                                                )}
                                                {member.social?.email && (
                                                    <IconButton size="small" href={`mailto:${member.social.email}`}>
                                                        <Email />
                                                    </IconButton>
                                                )}
                                                {member.social?.twitter && (
                                                    <IconButton size="small" href={member.social.twitter} target="_blank">
                                                        <Twitter />
                                                    </IconButton>
                                                )}
                                            </Stack>
                                        </CardContent>
                                    </Card>
                                </Zoom>
                            </Grid>
                        ))}
                    </Grid>
                </Box>

                {/* Version History */}
                <Box sx={{ mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Version History
                    </Typography>
                    <Paper elevation={1} sx={{ p: { xs: 2, sm: 3 } }}>
                        <Timeline>
                            {versionHistory.map((version, index) => (
                                <TimelineItem key={version.version}>
                                    <TimelineSeparator>
                                        <TimelineDot color="primary">
                                            <Update />
                                        </TimelineDot>
                                        {index < versionHistory.length - 1 && <TimelineConnector />}
                                    </TimelineSeparator>
                                    <TimelineContent>
                                        <Typography
                                            variant="h6"
                                            component="span"
                                            sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
                                        >
                                            Version {version.version}
                                        </Typography>
                                        <Typography variant="caption" display="block" color="text.secondary">
                                            {version.date}
                                        </Typography>
                                        <Typography
                                            variant="body2"
                                            sx={{
                                                mt: 1,
                                                mb: 1,
                                                fontSize: { xs: '0.85rem', sm: '0.875rem' }
                                            }}
                                        >
                                            {version.description}
                                        </Typography>
                                        <List dense>
                                            {version.features.map((feature) => (
                                                <ListItem key={feature} sx={{ py: 0 }}>
                                                    <ListItemIcon sx={{ minWidth: 32 }}>
                                                        <CheckCircle color="primary" fontSize="small" />
                                                    </ListItemIcon>
                                                    <ListItemText
                                                        primary={feature}
                                                        primaryTypographyProps={{
                                                            fontSize: { xs: '0.85rem', sm: '0.875rem' }
                                                        }}
                                                    />
                                                </ListItem>
                                            ))}
                                        </List>
                                    </TimelineContent>
                                </TimelineItem>
                            ))}
                        </Timeline>
                    </Paper>
                </Box>

                {/* System Requirements */}
                <Box sx={{ mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        System Requirements
                    </Typography>
                    <Grid container spacing={3}>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Card>
                                <CardHeader
                                    title="Minimum Requirements"
                                    titleTypographyProps={{
                                        fontSize: { xs: '1.1rem', sm: '1.25rem' }
                                    }}
                                />
                                <CardContent>
                                    <List>
                                        {Object.entries(systemRequirements.minimum).map(([key, value]) => (
                                            <ListItem key={key}>
                                                <ListItemIcon>
                                                    {key === 'cpu' && <Cpu size={20} />}
                                                    {key === 'memory' && <Memory />}
                                                    {key === 'storage' && <HardDrive size={20} />}
                                                    {key === 'browser' && <Public />}
                                                    {key === 'network' && <Network size={20} />}
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={key.charAt(0).toUpperCase() + key.slice(1)}
                                                    secondary={value}
                                                    primaryTypographyProps={{
                                                        fontSize: { xs: '0.9rem', sm: '1rem' }
                                                    }}
                                                    secondaryTypographyProps={{
                                                        fontSize: { xs: '0.8rem', sm: '0.875rem' }
                                                    }}
                                                />
                                            </ListItem>
                                        ))}
                                    </List>
                                </CardContent>
                            </Card>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Card>
                                <CardHeader
                                    title="Recommended Requirements"
                                    titleTypographyProps={{
                                        fontSize: { xs: '1.1rem', sm: '1.25rem' }
                                    }}
                                />
                                <CardContent>
                                    <List>
                                        {Object.entries(systemRequirements.recommended).map(([key, value]) => (
                                            <ListItem key={key}>
                                                <ListItemIcon>
                                                    {key === 'cpu' && <Cpu size={20} />}
                                                    {key === 'memory' && <Memory />}
                                                    {key === 'storage' && <HardDrive size={20} />}
                                                    {key === 'browser' && <Public />}
                                                    {key === 'network' && <Network size={20} />}
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={key.charAt(0).toUpperCase() + key.slice(1)}
                                                    secondary={value}
                                                    primaryTypographyProps={{
                                                        fontSize: { xs: '0.9rem', sm: '1rem' }
                                                    }}
                                                    secondaryTypographyProps={{
                                                        fontSize: { xs: '0.8rem', sm: '0.875rem' }
                                                    }}
                                                />
                                            </ListItem>
                                        ))}
                                    </List>
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>
                </Box>

                {/* FAQ Section */}
                <Box sx={{ mb: { xs: 4, md: 6 } }}>
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        textAlign="center"
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Frequently Asked Questions
                    </Typography>
                    <Box sx={{ mt: 3 }}>
                        {[
                            {
                                question: "What file formats does Magellon support?",
                                answer: "Magellon supports MRC, TIFF, JPEG, PNG, and other common scientific image formats. We're continuously adding support for additional formats based on user needs."
                            },
                            {
                                question: "Is Magellon free to use?",
                                answer: "Yes, Magellon is open-source and free for academic and research use. Commercial licenses are available for industrial applications."
                            },
                            {
                                question: "Can I use Magellon offline?",
                                answer: "Magellon requires an internet connection for initial setup and some cloud features, but core image viewing and analysis can work offline once data is cached locally."
                            },
                            {
                                question: "How do I report bugs or request features?",
                                answer: "Please use our GitHub issues page to report bugs or request new features. We also welcome contributions from the community!"
                            },
                            {
                                question: "What level of technical expertise is required?",
                                answer: "Magellon is designed to be user-friendly for researchers at all technical levels. Basic computer skills and familiarity with image analysis concepts are helpful but not required."
                            }
                        ].map((faq, index) => (
                            <Accordion key={index}>
                                <AccordionSummary expandIcon={<ExpandMore />}>
                                    <Typography
                                        variant="h6"
                                        sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}
                                    >
                                        {faq.question}
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Typography sx={{ fontSize: { xs: '0.9rem', sm: '1rem' } }}>
                                        {faq.answer}
                                    </Typography>
                                </AccordionDetails>
                            </Accordion>
                        ))}
                    </Box>
                </Box>

                {/* Contact and Support */}
                <Paper
                    elevation={2}
                    sx={{
                        p: { xs: 3, sm: 4 },
                        textAlign: 'center',
                        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.1)}, ${alpha(theme.palette.secondary.main, 0.1)})`
                    }}
                >
                    <Typography
                        variant={isMobile ? "h5" : "h4"}
                        gutterBottom
                        sx={{ fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' } }}
                    >
                        Get Involved
                    </Typography>
                    <Typography
                        variant="body1"
                        sx={{
                            mb: 3,
                            maxWidth: 600,
                            mx: 'auto',
                            fontSize: { xs: '0.9rem', sm: '1rem' }
                        }}
                    >
                        Magellon is a community-driven project. Whether you're a researcher, developer, or just interested in scientific computing, there are many ways to contribute!
                    </Typography>
                    <Grid container spacing={3} justifyContent="center">
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <Button
                                variant="outlined"
                                fullWidth
                                startIcon={<GitHub />}
                                href="https://github.com/magellon-project"
                                target="_blank"
                                size={isMobile ? "medium" : "large"}
                            >
                                Contribute Code
                            </Button>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <Button
                                variant="outlined"
                                fullWidth
                                startIcon={<BugReport />}
                                href="https://github.com/magellon-project/issues"
                                target="_blank"
                                size={isMobile ? "medium" : "large"}
                            >
                                Report Issues
                            </Button>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <Button
                                variant="outlined"
                                fullWidth
                                startIcon={<BookOpen />}
                                href="https://docs.magellon.org"
                                target="_blank"
                                size={isMobile ? "medium" : "large"}
                            >
                                Documentation
                            </Button>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <Button
                                variant="outlined"
                                fullWidth
                                startIcon={<Email />}
                                href="mailto:info@magellon.org"
                                size={isMobile ? "medium" : "large"}
                            >
                                Contact Us
                            </Button>
                        </Grid>
                    </Grid>

                    <Divider sx={{ my: 3 }} />

                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: 1,
                        flexWrap: 'wrap'
                    }}>
                        <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
                        >
                            Made with
                        </Typography>
                        <Heart size={16} color={theme.palette.error.main} />
                        <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
                        >
                            by scientists, for science
                        </Typography>
                        <Coffee size={16} color={theme.palette.warning.main} />
                    </Box>
                </Paper>
            </Box>
        </Box>
    );
};

export default AboutPage;