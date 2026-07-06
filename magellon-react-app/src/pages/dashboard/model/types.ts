import type { ReactElement } from 'react';

export type DashboardIcon = ReactElement<{ size?: number; color?: string }>;

export interface MetricChartProps {
    data: number[];
    color: string;
    height?: number;
}

export interface StatCardProps {
    title: string;
    value: string;
    subtitle?: string;
    icon: DashboardIcon;
    color: string;
    chartData?: number[];
}

export interface QuickActionCardProps {
    title: string;
    icon: DashboardIcon;
    color: string;
    onClick: () => void;
    featured?: boolean;
}

export type ActivityStatus = "default" | "success" | "warning" | "error" | "info";

export interface ActivityItemProps {
    icon: DashboardIcon;
    text: string;
    time: string;
    status?: ActivityStatus;
}

export type RecentlyViewedType = "image" | "session" | "project";

export interface RecentlyViewedItemProps {
    name: string;
    type: RecentlyViewedType;
    time: string;
    onClick: () => void;
}

export type ProjectStatus = "completed" | "in-progress" | "paused";

export interface ProjectCardProps {
    name: string;
    progress: number;
    status: ProjectStatus;
    lastUpdated: string;
    onClick: () => void;
}

export interface SystemResource {
    name: string;
    usage: number;
}
