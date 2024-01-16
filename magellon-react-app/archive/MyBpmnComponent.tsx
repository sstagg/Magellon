import React, { useEffect } from "react";
import BpmnModeler from "bpmn-js/lib/Modeler";
import {
    BpmnPropertiesPanelModule,
    BpmnPropertiesProviderModule,
} from "bpmn-js-properties-panel";

import '../node_modules/bpmn-js/dist/assets/bpmn-js.css'
import '../node_modules/bpmn-js/dist/assets/diagram-js.css'
import '../node_modules/bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css'
import '../node_modules/bpmn-js-properties-panel/dist/assets/properties-panel.css'

import zeebeModdleDescriptors from 'zeebe-bpmn-moddle/resources/zeebe.json';
import { ZeebePropertiesProviderModule } from 'bpmn-js-properties-panel';

const MyBpmnComponent = () => {
    useEffect(() => {
        const diagram = `
    <?xml version="1.0" encoding="UTF-8"?>
    <bpmn2:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" xsi:schemaLocation="http://www.omg.org/spec/BPMN/20100524/MODEL BPMN20.xsd" id="sample-diagram" targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn2:process id="Process_1" isExecutable="false">
        <bpmn2:startEvent id="StartEvent_1"/>
      </bpmn2:process>
      <bpmndi:BPMNDiagram id="BPMNDiagram_1">
        <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
          <bpmndi:BPMNShape id="_BPMNShape_StartEvent_2" bpmnElement="StartEvent_1">
            <dc:Bounds height="36.0" width="36.0" x="412.0" y="240.0"/>
          </bpmndi:BPMNShape>
        </bpmndi:BPMNPlane>
      </bpmndi:BPMNDiagram>
    </bpmn2:definitions>
    `;

        const bpmnModeler = new BpmnModeler({
            container: "#js-canvas",
            propertiesPanel: {
                parent: "#js-properties-panel",
            },
            additionalModules: [
                BpmnPropertiesPanelModule,
                BpmnPropertiesProviderModule,
                ZeebePropertiesProviderModule
            ],
            moddleExtensions: {
                //camunda: camundaModdleDescriptors
                zeebe: zeebeModdleDescriptors
            },
        });

        bpmnModeler.importXML(diagram);

        // Clean up the modeler instance when the component unmounts
        return () => {
            bpmnModeler.destroy();
        };
    }, []);

    return (
        <div style={{width:"100vw", display: "flex", height: "100vh" }}>
            <div
                className="canvas"
                id="js-canvas"
                style={{ flex: 1, height: "100%" }}
            ></div>
            <div
                className="properties-panel-parent"
                id="js-properties-panel"
                style={{ width: "400px", flexShrink: 0 }}
            ></div>
        </div>
    );
};

export default MyBpmnComponent;
