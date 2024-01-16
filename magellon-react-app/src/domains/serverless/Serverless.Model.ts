interface IServerlessCode {
    id: number;
    name: string;
    alias: string | null;
    code: string;
    description: string | null;
    runtime_id: number | null;
    author: string | null;
    copyright: string | null;
    requirements: string | null;
    created_at: Date;
    updated_at: Date;
    status_id: number | null;
    version: string | null;
}

export default IServerlessCode;
