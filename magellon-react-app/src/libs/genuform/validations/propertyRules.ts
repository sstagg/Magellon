// propertyRules.ts

export class PropertyRule {
    // @ts-ignore
    private _value: any;
    validate(value: any): boolean {
        this._value = value;
        throw new Error('Validation rule not implemented');
    }
}

export class EmailValidation extends PropertyRule {
    validate(value: any): boolean {
        // Implement email validation logic here
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(value);
    }
}

export class PasswordValidation extends PropertyRule {
    validate(value: any): boolean {
        // Implement password validation logic here
        return value.length >= 8;
    }
}

export class UsernameValidation extends PropertyRule {
    validate(value: any): boolean {
        // Implement username validation logic here
        return /^[a-zA-Z0-9_]+$/.test(value);
    }
}
