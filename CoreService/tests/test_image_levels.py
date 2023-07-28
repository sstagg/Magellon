import re


# regex_pattern = r'sq|gr|ex|hl|fc'  # Use your desired regex pattern here
#
# images = ['22apr01a_b_00016gr_00019sq_v01_00017hl_00001fc',
#           '22apr01a_b_00011gr_00003sq_v01_00003hl_00014ex-b-DW',
#           '22apr01a_b_00029gr_00017sq_v01_00019hl',
#           '22apr01a_b_00001hl',
#           '22apr01a_b_00001hl_00001ex',
#           '22apr01a_b_00016hl_00019gr_v01_00017sq']


# def infer_image_levels(name, regex_pattern):
#     matches = re.finditer(regex_pattern, name, re.IGNORECASE)
#     total_levels = sum(1 for _ in matches)
#     presets_sorted = sorted(matches, key=lambda x: x.start())
#     return total_levels, presets_sorted
#
#
# for image in images:
#     total_levels, presets_sorted = infer_image_levels(image, regex_pattern)
#     print("Image:", image)
#     print("Total levels =", total_levels)
#     print("Sorted presets:", [match.group() for match in presets_sorted])
#     print("\n")


# presets = [{'name': 'sq'}, {'name': 'gr'}, {'name': 'ex'}, {'name': 'hl'}, {'name': 'fc'}]
#
# images = ['22apr01a_b_00016gr_00019sq_v01_00017hl_00001fc', '22apr01a_b_00011gr_00003sq_v01_00003hl_00014ex-b-DW',
#           '22apr01a_b_00029gr_00017sq_v01_00019hl', '22apr01a_b_00001hl', '22apr01a_b_00001hl_00001ex',
#           '22apr01a_b_00016hl_00019gr_v01_00017sq']
#
# for image in images:
#
#     totallevels = 0
#     for preset in presets:
#         i = image.find(preset['name'])
#         if i >= 0:
#             totallevels += 1
#             preset['index'] = i
#         else:
#             preset['index'] = i
#
#     print(image)
#     print('total levels = ', totallevels)
#
#     presets_sorted = sorted(presets, key=lambda x: x['index'])
#     print(presets_sorted)
#     print('\n\n')

#
# def get_total_levels(images, presets):
#     results = []
#     for image in images:
#         total_levels = 0
#         for preset in presets:
#             i = image.find(preset['name'])
#             if i >= 0:
#                 total_levels += 1
#                 preset['index'] = i
#             else:
#                 preset['index'] = i
#
#         results.append((image, total_levels))
#
#     return results
#
#
# presets = [{'name': 'sq'}, {'name': 'gr'}, {'name': 'ex'}, {'name': 'hl'}, {'name': 'fc'}]
images = ['22apr01a_b_00016gr_00019sq_v01_00017hl_00001fc', '22apr01a_b_00011gr_00003sq_v01_00003hl_00014ex-b-DW',
          '22apr01a_b_00029gr_00017sq_v01_00019hl', '22apr01a_b_00001hl', '22apr01a_b_00001hl_00001ex',
          '22apr01a_b_00016hl_00019gr_v01_00017sq']
#
# results = get_total_levels(images, presets)
#
# for image, total_levels in results:
#     print(image)
#     print('total levels =', total_levels)
#
#     presets_sorted = sorted(presets, key=lambda x: x['index'])
#     print(presets_sorted)
#     print('\n\n')


def count_used_presets(input_string):
    presets = {'sq', 'gr', 'ex', 'hl', 'fc'}
    return sum(1 for preset in presets if preset in input_string)


# def count_presets_in_string(input_string):
#     presets = ['sq', 'gr', 'ex', 'hl', 'fc']
#     preset_counts = {preset: 0 for preset in presets}
#
#     for preset in presets:
#         preset_counts[preset] = input_string.count(preset)
#
#     return preset_counts


# Test the function
for image in images:
    print(count_used_presets(image))

# input_string = '22apr01a_b_00016gr_00019sq_v01_00017hl_00001fc'
# result = count_used_presets(input_string)
# print(result)
