from typing import Dict, Any



from lxml import etree
from io import BytesIO
from typing import List, Optional
from pydantic import BaseModel, Field
from services.importers.BaseImporter import  BaseImporter

class EPUMetadata(BaseModel):
    uniqueID: Optional[str] = None
    DoseOnCamera: Optional[float] = None
    Dose: Optional[float] = None
    Defocus: Optional[float] = None
    dimension_x: Optional[int] = None
    binning_x: Optional[int] = None #Field(None, alias="Binning/ns5:x")
    binning_y: Optional[int] = None #Field(None, alias="Binning/ns5:y")
    pixelSize_x: Optional[float] = None
    atlas_delta_row: Optional[float] = None
    atlas_delta_column: Optional[float] = None
    stage_alpha_tilt: Optional[float] = None
    stage_position_x: Optional[float] = None
    stage_position_y: Optional[float] = None

    class Config:
        allow_population_by_field_name = True

namespaces = {
    'ns0': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
    'ns1': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
    'ns2': 'http://schemas.datacontract.org/2004/07/Fei.Types',
    'ns3': 'http://schemas.datacontract.org/2004/07/System.Windows.Media',
    'ns4': 'http://schemas.datacontract.org/2004/07/Fei.Common.Types',
    'ns5': 'http://schemas.datacontract.org/2004/07/System.Drawing'
}


def parse_xml(xml_content: bytes) -> EPUMetadata:
    root = etree.parse(BytesIO(xml_content))
    metadata = {}

    xpath_mapping = {
        'uniqueID': './/ns0:uniqueID',
        'DoseOnCamera': './/ns0:DoseOnCamera',
        'Dose': './/ns0:Dose',
        'Defocus': './/ns0:Defocus',
        'dimension_x': './/ns0:dimension/ns0:width',
        'binning_x': './/ns0:Binning/ns5:x',
        'binning_y': './/ns0:Binning/ns5:y',
        'pixelSize_x': './/ns0:pixelSize/ns0:x/ns0:numericValue',
        'atlas_delta_row': './/ns0:atlas_delta_row',
        'atlas_delta_column': './/ns0:atlas_delta_column',
        'stage_alpha_tilt': './/ns0:stage_alpha_tilt',
        'stage_position_x': './/ns0:stage/ns0:Position/ns0:X',
        'stage_position_y': './/ns0:stage/ns0:Position/ns0:Y'
    }

    for field, xpath in xpath_mapping.items():
        element = root.find(xpath, namespaces)
        if element is not None:
            value = element.text
            # Convert to appropriate type
            if field in ['dimension_x', 'binning_x', 'binning_y']:
                metadata[field] = int(value) if value else None
            elif 'position' in field or field in ['DoseOnCamera', 'Dose', 'Defocus', 'pixelSize_x', 'atlas_delta_row', 'atlas_delta_column', 'stage_alpha_tilt']:
                metadata[field] = float(value) if value else None
            else:
                metadata[field] = value

    return EPUMetadata(**metadata)



class EPUImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.image_tasks = []

    def import_data(self):
        # Implement EPU-specific data import logic
        # This might involve parsing XML files
        pass

    def process_imported_data(self):
        # Implement EPU-specific data processing logic
        pass

    def get_image_tasks(self):
        return self.image_tasks

    def parse_epu_xml(self, xml_content: bytes):
        # Use the existing parse_xml function
        # return create_epu_metadata(parse_xml(xml_content))
        return parse_xml(xml_content)