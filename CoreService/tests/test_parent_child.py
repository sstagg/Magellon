import re

def get_parent_name(child_name):
    split_name = child_name.split('_')
    # if split_name[-1] == 'v01':
    if re.search(r'[vV]([0-9][0-9])', split_name[-1]):
        parent_name = '_'.join(split_name[:-2])
    else:
        parent_name = '_'.join(split_name[:-1])
    # Join the parts back together with underscores and return
    return parent_name


# Example usage:
child_parent_pairs = [
    ("23apr13a_a_00043gr_00004sq_v01_00016hl_00001fc", "23apr13a_a_00043gr_00004sq_v01_00016hl"),
    ("23apr13a_a_00043gr_00008sq_v01_00021hl_00003ex", "23apr13a_a_00043gr_00008sq_v01_00021hl"),
    ("23apr13a_a_00043gr_00023sq_v01_00003hl_00007ex", "23apr13a_a_00043gr_00023sq_v01_00003hl"),
    ("23apr13a_a_00042gr_00020sq_v01_00015hl_00004ex", "23apr13a_a_00042gr_00020sq_v01_00015hl"),
    ("23apr13a_a_00043gr_00008sq_v01_00015hl", "23apr13a_a_00043gr_00008sq_v01"),
    ("23apr13a_a_00043gr_00008sq_v01", "23apr13a_a_00043gr"),
    ("23apr13a_a_00042gr_00021sq_v01_00013hl_00001fc", "23apr13a_a_00042gr_00021sq_v01_00013hl"),
    ("23apr13a_a_00044gr_00003sq_v01_00002hl", "23apr13a_a_00044gr_00003sq_v01"),
    ("23apr13a_a_00044gr", "23apr13a_a"),
    ("23apr13a_a_00042gr_00021sq_v01_00015hl_00002ex", "23apr13a_a_00042gr_00021sq_v01_00015hl"),
    ("23apr13a_a_00042gr_00019sq_v01_00015hl", "23apr13a_a_00042gr_00019sq_v01"),
    ("23apr13a_a_00043gr_00012sq_v01_00008hl_00002ex", "23apr13a_a_00043gr_00012sq_v01_00008hl")
]

for child, parent in child_parent_pairs:
    print(f"Parent for child {child} is: {get_parent_name(child)}")
    if get_parent_name(child)!=parent:
        print("NO")
