import {z, ZodError, ZodSchema} from "zod";


export interface IEntity {
    // Define the common properties for all entities here
    validate(): { isValid: boolean; errors: Record<string, string> };
    schema: ZodSchema<any>;
}

export const IEntityValidation = {
    validate(entity: IEntity): { isValid: boolean; errors: Record<string, string> } {
        try {
            entity.schema.parse(entity); // Use the provided schema to validate the entity
            return { isValid: true, errors: {} };
        } catch (error) {
            if (error instanceof ZodError) {
                const errors: Record<string, string> = {};

                error.errors.forEach((validationError) => {
                    if (validationError.path) {
                        const fieldName = validationError.path[0];
                        const errorMessage = validationError.message;
                        errors[fieldName] = errorMessage;
                    }
                });

                return { isValid: false, errors };
            } else {
                throw error; // Rethrow the error if it's not a ZodError
            }
        }
    },
};