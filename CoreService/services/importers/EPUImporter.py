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

fields = {
    'uniqueID': None,
    'DoseOnCamera': None,
    'Dose': None,
    'Defocus': None,
    'dimension_x': None,
    'Binning/ns5:x': None,
    'Binning/ns5:y': None,
    'pixelSize/ns0:x/ns0:numericValue': None,
    'atlas_delta_row': None,
    'atlas_delta_column': None,
    'stage_alpha_tilt': None,
    'stage/ns0:Position/ns0:X': None,
    'stage/ns0:Position/ns0:Y': None,
}
# Function to create EPUMetadata from a dictionary
def create_epu_metadata(fields: dict) -> EPUMetadata:
    # Create an instance of EPUMetadata using the dictionary values
    return EPUMetadata(
        uniqueID=fields.get('uniqueID'),
        DoseOnCamera=fields.get('DoseOnCamera'),
        Dose=fields.get('Dose'),
        Defocus=fields.get('Defocus'),
        dimension_x=fields.get('dimension_x'),
        binning_x=fields.get('Binning/ns5:x'),
        binning_y=fields.get('Binning/ns5:y'),
        pixelSize_x=fields.get('pixelSize/ns0:x/ns0:numericValue'),
        atlas_delta_row=fields.get('atlas_delta_row'),
        atlas_delta_column=fields.get('atlas_delta_column'),
        stage_alpha_tilt=fields.get('stage_alpha_tilt'),
        stage_position_x=fields.get('stage/ns0:Position/ns0:X'),
        stage_position_y=fields.get('stage/ns0:Position/ns0:Y')
    )


def parse_xml(xml_content: bytes) -> Dict[str, Any]:
    root = etree.parse(BytesIO(xml_content))
    results = fields.copy()

    for e in root.iter():
        path = root.getelementpath(e)

        for n in namespaces:
            path = path.replace('{'+namespaces[n]+'}', n+':')

        for field in fields:
            if path.endswith(':'+field):
                val = root.find('.//' + path, namespaces)
                results[field] = val.text if val is not None else None
            if path.endswith(':Key'):
                val = root.find('.//' + path, namespaces)
                if val is not None and val.text in fields:
                    value_path = path.replace(']/ns1:Key', ']/ns1:Value')
                    value = root.find('.//' + value_path, namespaces)
                    results[val.text] = value.text if value is not None else None

    return results



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
        return create_epu_metadata(parse_xml(xml_content))