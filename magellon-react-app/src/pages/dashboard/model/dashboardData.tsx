import {
    AlertCircle,
    Brain,
    CheckCircle,
    Cpu,
    Database,
    FileText,
    Image as ImageIcon,
    Settings,
    Upload
} from 'lucide-react';
import type {
    ActivityItemProps,
    ProjectCardProps,
    RecentlyViewedItemProps,
    StatCardProps,
    SystemResource
} from './types.ts';

// Demo data for the stats cards
export const initialStats: StatCardProps[] = [
    {
        title: "Total Projects",
        value: "14",
        subtitle: "+2 this month",
        icon: <FileText />,
        color: "#67e8f9",
        chartData: [3, 6, 5, 8, 4, 7, 9, 5, 10, 12, 11, 14]
    },
    {
        title: "Active Sessions",
        value: "3",
        subtitle: "From 2 sessions",
        icon: <Database />,
        color: "#818cf8",
        chartData: [2, 3, 3, 4, 3, 5, 4, 3, 1, 3, 2, 3]
    },
    {
        title: "Processing Jobs",
        value: "7",
        subtitle: "5 completed",
        icon: <Cpu />,
        color: "#8b5cf6",
        chartData: [12, 9, 8, 10, 7, 5, 6, 8, 9, 4, 5, 7]
    },
    {
        title: "Processed Images",
        value: "2.4k",
        subtitle: "+340 today",
        icon: <ImageIcon />,
        color: "#a78bfa",
        chartData: [400, 600, 800, 950, 1200, 1350, 1500, 1680, 1890, 2100, 2250, 2400]
    }
];

// Mock activity data
export const activities: ActivityItemProps[] = [
    {
        icon: <CheckCircle />,
        text: "Job #421 (2D Classification) completed",
        time: "10 minutes ago",
        status: "success"
    },
    {
        icon: <Upload />,
        text: "Imported 156 new images from Session #3",
        time: "45 minutes ago",
        status: "info"
    },
    {
        icon: <Settings />,
        text: "System maintenance scheduled for tonight",
        time: "2 hours ago",
        status: "warning"
    },
    {
        icon: <Brain />,
        text: "Particle picking completed for Dataset A",
        time: "Yesterday at 4:15 PM",
        status: "success"
    },
    {
        icon: <AlertCircle />,
        text: "Storage usage approaching 80% capacity",
        time: "Yesterday at 11:30 AM",
        status: "warning"
    }
];

// Mock projects data
export const projects: Omit<ProjectCardProps, "onClick">[] = [
    {
        name: "COVID-19 Spike Protein",
        progress: 85,
        status: "in-progress",
        lastUpdated: "Today at 9:45 AM"
    },
    {
        name: "Ribosome Structure Analysis",
        progress: 100,
        status: "completed",
        lastUpdated: "Yesterday at 3:12 PM"
    },
    {
        name: "Membrane Protein Study",
        progress: 45,
        status: "in-progress",
        lastUpdated: "May 19, 2025"
    }
];

// Mock recently viewed data
export const recentlyViewed: Omit<RecentlyViewedItemProps, "onClick">[] = [
    {
        name: "24may21_Sample459-01_00039gr",
        type: "image",
        time: "12 minutes ago"
    },
    {
        name: "Ribosome Dataset (May 2025)",
        type: "session",
        time: "3 hours ago"
    },
    {
        name: "Membrane Protein Analysis",
        type: "project",
        time: "Yesterday at 5:30 PM"
    }
];

// System resource usage
export const systemResources: SystemResource[] = [
    { name: "CPU", usage: 24 },
    { name: "Memory", usage: 42 },
    { name: "Storage", usage: 68 },
    { name: "Network", usage: 35 }
];
