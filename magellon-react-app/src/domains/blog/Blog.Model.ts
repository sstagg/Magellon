import {IEntity, IEntityValidation} from "../../core/IEntity.ts";
import {undefined, z, ZodError, ZodType} from "zod";
export interface ObjectBase {
    omid?   :number,
}

export interface IBlog extends IEntity {
    userId?: number;
    id?: number;
    title?: string;
    body?: string;
}

const IBlogSchema = z.object({
    userId: z.optional(z.number()),
    id: z.optional(z.number()),
    title: z.optional(z.string()),
    body: z.optional(z.string()),
});


export class Blog implements IEntity {
    userId?: number;
    id?: number;
    title?: string;
    body?: string;

    constructor(data: Partial<IBlog>) {
        this.userId = data.userId;
        this.id = data.id;
        this.title = data.title;
        this.body = data.body;
    }

    // Define the Zod schema for Blog
    private static schema = IBlogSchema;

    // Implement the IEntity interface method for validation
    validate(): { isValid: boolean; errors: Record<string, string> } {
        return IEntityValidation.validate(this);
    }
}

// export class Blog implements IBlog {
//     constructor() {}
//
//     schema: IBlogSchema;
//
//     validate(): {
//         isValid: boolean;
//         errors: Record<string, string>
//     } {
//         return {errors: undefined, isValid: false};
//     }
// }
export const defaultValue: Readonly<IBlog> = {

}