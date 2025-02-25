import re

def extract_data_from_file(file_path, keys):
    result = {new_key: None for _, new_key in keys}
    
    with open(file_path, 'r') as file:
        for line in file:
            match = re.match(r"(\w+) = (.+)", line)
            if match:
                file_key, value = match.groups()
                    
                # Handle StagePosition as a special case (it has two values)
                # StagePosition = 792.824 -213.633, first is stage x second is stage y
                if file_key == "StagePosition":
                    x, y = map(float, value.split())
                    for orig_key, new_key in keys:
                        if orig_key == "StagePosition":
                            if new_key == "stage_x":
                                result[new_key] = x
                            elif new_key == "stage_y":
                                result[new_key] = y
                else:
                    for orig_key, new_key in keys:
                        if orig_key == file_key:
                            try:
                                result[new_key] = float(value) if '.' in value or value.isdigit() else value
                            except ValueError:
                                result[new_key] = value
    
    return result

keys = [
    ('oid', 'oid'),
    ('name', 'name'),
    ('Magnification', 'magnification'),
    ('Defocus', 'defocus'),
    ('DoseRate', 'dose'),
    ('PixelSpacing', 'pixel_size'),
    ('binning_x', 'binning_x'),
    ('binning_y', 'binning_y'),
    ('TiltAngle', 'stage_alpha_tilt'),
    ('StagePosition', 'stage_x'),
    ('StagePosition', 'stage_y'),
    ('Voltage', 'acceleration_voltage'),
    ('atlas_dimxy', 'atlas_dimxy'),
    ('atlas_delta_row', 'atlas_dimxy'),
    ('atlas_delta_column', 'atlas_delta_column'),
    ('level', 'level'),
    ('previous_id', 'previous_id'),
    ('spherical_aberration', 'spherical_aberration'),
    ('session_id', 'session_id')
]

file_path = "20220605_75157_20220605-aav2spr_1-1_counted_frames.mrc.mdoc"
result = extract_data_from_file(file_path, keys)
for item in result:
    print(f"{item}: {result[item]}")