import {GenuType, IGenuWidgetProps,IGenuComponent} from "./GenuType.ts";
import React from "react";
import GenuNumberEditor from "./editors/GenuNumberEditor.tsx";


class EditorInjector {

    public components: IGenuComponent[] = []; // Array to store registered components
    public editorMapping: { [key in GenuType]: Set<IGenuComponent> } = {};

    constructor() {
        // Initialize an empty Set for each GenuType in the constructor
        for (const type of Object.values(GenuType)) {
            this.editorMapping[type] = new Set();
        }
    }
    //gets typescript type and returns name of the editor
    public getFirstEditorNameForType(type: string): string | null {
        const genuType = this.mapTypeToGenuType(type);
        const editors = this.editorMapping[genuType];

        if (editors && editors.size > 0) {
            const firstEditor = editors.values().next().value;
            return firstEditor.constructor.name;
        }
        return null; // No editors found for the given type
    }

    private addToEditorMapping(editor: IGenuComponent): void {
        // debugger;
        for (const theType of editor.allowedTypes) {
            const genuType = this.mapTypeToGenuType(theType);
            this.editorMapping[genuType].add(editor);
        }
    }

    private FillGenuTypeEditors(): void {
        // Iterate through registered components
        for (const theEditor of this.components) {
            this.addToEditorMapping(theEditor);
        }
    }

    // static editorComponents: Record<string, React.ComponentType<IGenuWidgetProps>> = {
    //     GenuNumberEditor: GenuNumberEditor,
    //     // GenuTextBoxEditor: GenuTextBoxEditor,
    //     // Add more initial editor components here
    // };
    // static addEditorComponent(name: string, component: React.ComponentType<IGenuWidgetProps>) {
    //     EditorInjector.editorComponents[name] = component;
    // }
    //
    // static getEditorByName(name: string, widget: IGenuWidgetProps) {
    //     const selectedEditor = EditorInjector.editorComponents[name];
    //
    //     if (!selectedEditor) {
    //         return null; // Return null if the editor name isn't found
    //     }
    //
    //     const EditorComponent = selectedEditor;
    //
    //     return <EditorComponent } />;
    // }

    private mapTypeToGenuType(type: string): GenuType {
        switch (type) {
            case "string":
                return GenuType.STRING;
            case "number":
                return GenuType.DOUBLE;
            case "boolean":
                return GenuType.BOOL;
            case "bigint":
                return GenuType.INT64;
            case "symbol":
            case "object":
            case "undefined":
            case "function":
            default:
                return GenuType.STRING;
        }
    }

    // Method: Register a component to the form
    public registerComponent(component: IGenuComponent): void {
        this.components.push(component);
        this.addToEditorMapping(component);
    }
}

export default EditorInjector;