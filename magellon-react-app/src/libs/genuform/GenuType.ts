
interface IGenuComponent {
    allowedTypes: GenuType[];
}
interface IGenuWidgetProps {
    name: string;
    caption: string;
    value: any;
    onValueChanging(oldValue: any, newValue: any): number;
    onValueChanged(oldValue: any, newValue: any): number;
}
// This is a visual component unidirectional binding / reads only like charts
interface IGenuDisplayWidgetProps extends IGenuWidgetProps {    //label , chart , static image}
}
// Interface: IGenuEditor - Defines editors with value change events read write values
interface IGenuPropertyEditorProps extends IGenuWidgetProps {
}
// Interface: IGenuSoloEditor - Defines solo editors (editors modifying primitive values)
interface IGenuSoloEditorProps extends IGenuPropertyEditorProps {
    // Additional properties for solo editors
}
interface IGenuListEditorProps extends IGenuPropertyEditorProps {   // Additional properties for list editors}
}



class GenuFormItemProps {
    public name: string = ''; // Public property with default value
    public caption: string = ''; // Public property with default value
    public isVisible: boolean = true; // Default visibility is true
    public isEnabled: boolean = true; // Default enabled status is true
    public captionLocation: CaptionLocation = CaptionLocation.NONE; // Default caption location is none

    public minWidth: number = 0; // Default minimum width
    public minHeight: number = 0; // Default minimum height

    public offset: number = 0; // Default offset
    public xsColumns: number = 12; // Default columns for extra small screens
    public smColumns: number = 6; // Default columns for small screens
    public mdColumns: number = 4; // Default columns for medium screens
    public lgColumns: number = 3; // Default columns for large screens
    public xlColumns: number = 2; // Default columns for extra large screens
}


// Class: GenuGroupFormItem - Represents a group of form items with spacing and caption
class GenuGroupFormItemProps extends GenuFormItemProps {
    public items: GenuFieldFormItemProps[] = []; // Should this be an array of GenuFieldFormItem?
    public rowSpacing: number = 10; // Default row spacing
    public colSpacing: number = 10; // Default column spacing
}

// Class: GenuTabPageFormItem - Represents a tab page within a tab group
class GenuTabPageFormItemProps extends GenuGroupFormItemProps {
    // Similar properties to GenuGroupFormItem
}

// Class: GenuTabFormItem - Represents a tab group containing tab pages
class GenuTabFormItem extends GenuFormItemProps {
    public pages: GenuTabPageFormItemProps[] = []; // Array of tab pages
}

class GenuFieldFormItemProps extends GenuFormItemProps {

    public widget: string | null=null;//IGenuWidget; // Optional associated component
    public field :string='';
    public info: string = '';
    public warning: string = '';
    public error: string = '';
}





export enum GenuType {
    INT8,
    INT16,
    INT32,
    INT64,
    INT128,
    UINT8,
    UINT16,
    UINT32,
    UINT64,
    UINT128,
    BOOL,
    CHAR,
    STRING,
    FLOAT,
    DOUBLE,
    DECIMAL,
    BIGDECIMAL,
    MONEY,
    UUID,
    DATE,
    DATETIME,
    TIME,
    TIMESPAN,
    INTERVAL,
    BYTEARRAY,
    IMAGE,
    CHARARRAY,
    JSON,
    JSONB,
    XML,
    SVG,
    BSON,
    PROTOBUF,
    AVRO,
    GEOPOINT,
    GEOLINE,
    GEOPOLY,
    GEOPOINTS,
    GEOLINES,
    GEOPOLYS,
    GEOGRAPHY,
    GEOMETRY,
}


export enum CaptionLocation {
    RIGHT,
    LEFT,
    ABOVE,
    BOTTOM,
    NONE
}

export function mapTypeToGenuType(type: string): GenuType {
    switch (type) {
        case 'string':
            return GenuType.STRING;
        case 'number':
            return GenuType.DOUBLE;
        case 'boolean':
            return GenuType.BOOL;
        case 'bigint':
            return GenuType.INT64;
        case 'symbol':
        case 'object':
        case 'undefined':
        case 'function':
        default:
            return GenuType.STRING;
    }
}

export {
    IGenuComponent,
    IGenuWidgetProps,
    IGenuDisplayWidgetProps,
    IGenuPropertyEditorProps,
    IGenuSoloEditorProps,
    IGenuListEditorProps,
    GenuFormItemProps,
    GenuGroupFormItemProps,
    GenuTabPageFormItemProps,
    GenuTabFormItem,
    GenuFieldFormItemProps,
};
