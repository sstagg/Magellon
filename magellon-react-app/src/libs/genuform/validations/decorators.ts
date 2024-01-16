// decorators.ts

import { EmailValidation, PasswordValidation, UsernameValidation, PropertyRule } from './propertyRules';
import "reflect-metadata";


export const decoratorA = (someBooleanFlag: boolean) => {
    return (target: Function) => {
        console.log("target is here", target);
    }
}


export const allowlistOnly = (allowlist: string[]) => {
    return (target: any, memberName: string) => {

        let currentValue: any = target[memberName];
        console.log("target => ", target);
        // debugger;

        Object.defineProperty(target, memberName, {
            set: (newValue: any) => {
                // debugger;
                if (!allowlist.includes(newValue)) {
                    return;
                }
                currentValue = newValue;
            },
            get: () => currentValue
        });
    };
}

// export function GenuMin() {
//     return function(target: Function, context: any) {
//         if (context.kind === "method") {
//             return function (...args: any[]) {
//                 if (this.fuel > fuel) {
//                     return target.apply(this, args)
//                 } else {
//                     console.log(`Not enough fuel. Required: ${fuel}, got ${this.fuel}`)
//                 }
//             }
//         }
//     }
// }

export function EmailValidator() {
    return function(target: any, propertyKey: string | undefined) {
        if (propertyKey){
            const emailValidator = new EmailValidation();
            Reflect.defineMetadata("email-decorator", "{'type':'email'}", target, propertyKey);
            console.log("target is ", target, propertyKey);
            // applyValidationRule(target, propertyKey, emailValidator);
        }
    };
}

export function PasswordValidationDecorator() {
    return function(target: any, propertyKey: string) {
        const passwordValidator = new PasswordValidation();
        applyValidationRule(target, propertyKey, passwordValidator);
    };
}

export function UsernameValidationDecorator() {
    return function(target: any, propertyKey: string) {
        const usernameValidator = new UsernameValidation();
        applyValidationRule(target, propertyKey, usernameValidator);
    };
}

function applyValidationRule(target: any, propertyKey: string, rule: PropertyRule) {
    if (!target.__validationRules) {
        target.__validationRules = {};
    }

    target.__validationRules[propertyKey] = rule;
}
