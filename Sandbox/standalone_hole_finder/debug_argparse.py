import argparse
parser = argparse.ArgumentParser()
parser.add_argument('method', choices=['edge', 'template'])
parser.add_argument('image_path', nargs='?', help='image file')
parser.add_argument('--input', dest='image_path', help='image file')
args = parser.parse_args()
print(args)
