import xml.etree.ElementTree as ET

def parse_xml(file_path, keys, namespaces):
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Dictionary to store the results, initialize all values to None
    extracted_data = {key[1]: None for key in keys}

    for key in keys:
        for ns_prefix in namespaces:
            direct_element = root.find(f".//{ns_prefix}:{key[0]}", namespaces)
            if direct_element is not None:
                extracted_data[key[1]] = direct_element.text
                break

        for ns_prefix in namespaces:
            key_value_pairs = root.findall(f".//{ns_prefix}:KeyValueOfstringanyType", namespaces)
            for pair in key_value_pairs:
                key_element = pair.find(f"{ns_prefix}:Key", namespaces)
                value_element = pair.find(f"{ns_prefix}:Value", namespaces)
                if key_element is not None and value_element is not None and key_element.text == key[0]:
                    extracted_data[key[1]] = value_element.text
                    break

    return extracted_data


# Filepath
file_path = "Example1.xml"

# Keys to extract
#element 1 of tuple = name in xml
#element 2 of tuple = name in Magellon
keys = [('uniqueID', 'oid'),
          ('name', 'name'),
          ('NominalMagnification', 'magnification'),
          ('Defocus','defocus'),
          ('Dose', 'dose'),
          ('pixelSize/ns0:x/ns0:numericValue', 'pixel_size'),
          ('Binning/ns5:x', 'binning_x'),
          ('Binning/ns5:y', 'binning_y'),
          ('stage/ns0:Position/ns0:A', 'stage_alpha_tilt'),
          ('stage/ns0:Position/ns0:X', 'stage_x'),
          ('stage/ns0:Position/ns0:Y', 'stage_y'),
          ('AccelerationVoltage', 'acceleration_voltage'),
          ('atlas_dimxy', 'atlas_dimxy'),
          ('atlas_delta_row', 'atlas_dimxy'),
          ('atlas_delta_column', 'atlas_delta_column'),
          ('level', 'level'),
          ('previous_id', 'previous_id'),
          ('spherical_aberration', 'spherical_aberration'),
          ('session_id', 'session_id')
          ]

# Namespaces in the XML
namespaces = {
    'ns0': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
    'ns1': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
    'ns2': 'http://schemas.datacontract.org/2004/07/Fei.Types',
    'ns3': 'http://schemas.datacontract.org/2004/07/System.Windows.Media',
    'ns4': 'http://schemas.datacontract.org/2004/07/Fei.Common.Types',
    'ns5': 'http://schemas.datacontract.org/2004/07/System.Drawing'
}

data = parse_xml(file_path, keys, namespaces)

for key in data.keys():
    print(f"{key}: {data[key]}")

