import React from "react";
import {IGenuWidgetProps} from "./GenuType.ts";
import GenuNumberEditor from "./editors/GenuNumberEditor.tsx";

export class GenuEditorsFactory {
    static mEditorComponents: Record<string, React.ComponentType<IGenuWidgetProps>> = {
        GenuNumberEditor: GenuNumberEditor,
        // GenuTextBoxEditor: GenuTextBoxEditor,
        // Add more initial editor components here
    };

    static addEditorComponent(name: string, component: React.ComponentType<IGenuWidgetProps>) {
        GenuEditorsFactory.mEditorComponents[name] = component;
    }

    static getEditorByName(name, widget: IGenuWidgetProps) {
        const selectedEditor = GenuEditorsFactory.mEditorComponents[name];

        if (!selectedEditor) {
            return null; // Return null if the editor name isn't found
        }

        const EditorComponent = selectedEditor;

        return <EditorComponent caption={widget.caption}/>;
    }
}