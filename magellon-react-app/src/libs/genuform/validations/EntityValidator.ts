
import 'reflect-metadata';
class EntityValidator {
    static process(instance: any) {
        const propertyNames = Object.getOwnPropertyNames(instance);

        propertyNames.forEach(propertyName => {
            const decorators = Reflect.getMetadataKeys(instance, propertyName);
            console.log(`Property: ${propertyName}, Decorators: ${decorators.join(', ')}`);
            decorators.forEach(decorator => {
                // debugger;
                const mks = Reflect.getMetadata(decorator,instance, propertyName);
                console.log(mks);
            })


        });
    }
}

export default EntityValidator;
